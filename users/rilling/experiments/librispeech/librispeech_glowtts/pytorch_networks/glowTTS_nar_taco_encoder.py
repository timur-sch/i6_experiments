from dataclasses import dataclass
import torch
from torch import nn
import multiprocessing
import math
import os
import soundfile
import typing

from IPython import embed

from returnn.datasets.hdf import SimpleHDFWriter

from . import modules
from . import commons
from . import attentions
from .monotonic_align import maximum_path

from .feature_extraction import DbMelFeatureExtraction
from ..glowTTS.feature_config import DbMelFeatureExtractionConfig
from .eval_forward import *

class Config:
    def __init__(self, **kwargs):
        pass

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

@dataclass()
class NarEncoderConfig(Config):
    label_in_dim: int
    embedding_size: int
    conv_hidden_size: int
    filter_size: int
    dropout: float
    lstm_size: int

# This needs to be seperately defined here due to naming issues
# Accidentally renamed ln to norm in the nar_taco models, which breaks the forwarding
class Conv1DBlock(torch.nn.Module):
    """
    A 1D-Convolution with ReLU, batch-norm and non-broadcasted p_dropout
    Will pad to the same output length
    """

    def __init__(self, in_size, out_size, filter_size, p_dropout, norm="layer"):
        """
        :param in_size: input feature size
        :param out_size: output feature size
        :param filter_size: filter size
        :param p_dropout: dropout probability
        """
        super().__init__()
        assert filter_size % 2 == 1, "Only odd filter sizes allowed"
        self.conv = nn.Conv1d(in_size, out_size, filter_size, padding=filter_size // 2)
        self.norm = modules.LayerNorm(channels=out_size)
            
        self.p_dropout = p_dropout

    def forward(self, x_with_mask):
        """
        :param x: [B, F_in, T]
        :return: [B, F_out, T]
        """
        x, x_mask = x_with_mask
        x = self.conv(x * x_mask)
        x = nn.functional.relu(x)
        x = self.norm(x) # Layer normalization
        x = nn.functional.dropout(x, p=self.p_dropout, training=self.training)
        return (x, x_mask)


class DurationPredictor(nn.Module):
    """
    Duration Predictor module, trained using calculated durations coming from monotonic alignment search
    """

    def __init__(self, in_channels, filter_channels, filter_size, p_dropout):
        super().__init__()

        self.in_channels = in_channels
        self.filter_channels = filter_channels
        self.filter_size = filter_size
        self.p_dropout = p_dropout

        self.convs = nn.Sequential(
            Conv1DBlock(
                in_size=self.in_channels,
                out_size=self.filter_channels,
                filter_size=self.filter_size,
                p_dropout=p_dropout,
            ),
            Conv1DBlock(
                in_size=self.filter_channels,
                out_size=self.filter_channels,
                filter_size=self.filter_size,
                p_dropout=p_dropout,
            ),
        )
        self.proj = nn.Conv1d(in_channels=self.filter_channels, out_channels=1, kernel_size=1)

    def forward(self, x, x_mask):
        x_with_mask = (x, x_mask)
        (x, x_mask) = self.convs(x_with_mask)
        x = self.proj(x * x_mask)
        return x

class NarTacoEncoder(torch.nn.Module):
    """

    """

    def __init__(self, config: NarEncoderConfig):
        super().__init__()
        self.embedding = nn.Embedding(config.label_in_dim, config.embedding_size)
        self.encoder_convs = nn.Sequential(
            modules.Conv1DBlockBN(config.embedding_size, config.conv_hidden_size,
                        filter_size=config.filter_size, dropout=config.dropout),
            modules.Conv1DBlockBN(config.conv_hidden_size, config.conv_hidden_size, filter_size=config.filter_size, dropout=config.dropout),
            modules.Conv1DBlockBN(config.conv_hidden_size, config.conv_hidden_size, filter_size=config.filter_size, dropout=config.dropout),
        )
        self.blstm = nn.LSTM(input_size=config.conv_hidden_size, hidden_size=config.lstm_size, bidirectional=True, batch_first=True)

        self.output_size = 2*config.lstm_size

    def forward(self, label_in, label_in_len):
        """

        :param label_in: [B, N]
        :param label_in_len: [B]
        :return [B, N, lstm_size * 2]
        """
        transformed_labels = self.embedding(label_in)  # [B, N, embedding_size]
        transformed_labels_transposed = torch.transpose(transformed_labels, 1, 2)  # [B, embedding_size, N]
        conv_out = self.encoder_convs(transformed_labels_transposed)  # [B, conv_hidden_size, N]
        blstm_in = torch.transpose(conv_out, 1, 2) # [B, N, conv_hidden_size]

        # Sequences are sorted by decoder length, so here we do no sorting
        blstm_packed_in = nn.utils.rnn.pack_padded_sequence(blstm_in, label_in_len.to("cpu"), batch_first=True, enforce_sorted=False)
        blstm_packed_out, _ = self.blstm(blstm_packed_in)
        blstm_out, _ = nn.utils.rnn.pad_packed_sequence(
            blstm_packed_out, padding_value=0.0, batch_first=True
        )  # [B, N, lstm_size*2]

        return blstm_out

class TextEncoder(nn.Module):
    """
    Text Encoder model
    """

    def __init__(
        self,
        encoder_config: NarEncoderConfig,
        out_channels,
        filter_channels_dp,
        kernel_size,
        p_dropout,
        mean_only=False,
        gin_channels=0
    ):
        """Text Encoder Model based on Multi-Head Self-Attention combined with FF-CCNs

        Args:
            n_vocab (int): Size of vocabulary for embeddings
            out_channels (int): Number of output channels
            hidden_channels (int): Number of hidden channels
            filter_channels (int): Number of filter channels
            filter_channels_dp (int): Number of filter channels for duration predictor
            n_heads (int): Number of heads in encoder's Multi-Head Attention
            n_layers (int): Number of layers consisting of Multi-Head Attention and CNNs in encoder
            kernel_size (int): Kernel Size for CNNs in encoder layers
            p_dropout (float): Dropout probability for both encoder and duration predictor
            window_size (int, optional): Window size  in Multi-Head Self-Attention for encoder. Defaults to None.
            block_length (_type_, optional): Block length for optional block masking in Multi-Head Attention for encoder. Defaults to None.
            mean_only (bool, optional): Boolean to only project text encodings to mean values instead of mean and std. Defaults to False.
            prenet (bool, optional): Boolean to add ConvReluNorm prenet before encoder . Defaults to False.
            gin_channels (int, optional): Number of channels for speaker condition. Defaults to 0.
        """
        super().__init__()
        self.encoder_config = NarEncoderConfig.from_dict(encoder_config)
        self.out_channels = out_channels
        self.hidden_channels = 2*self.encoder_config.lstm_size
        self.filter_channels_dp = filter_channels_dp
        self.kernel_size = kernel_size
        self.p_dropout = p_dropout
        self.mean_only = mean_only
        self.gin_channels = gin_channels


        self.encoder = NarTacoEncoder(self.encoder_config)

        self.proj_m = nn.Conv1d(self.hidden_channels, out_channels, 1)
        if not mean_only:
            self.proj_s = nn.Conv1d(self.hidden_channels, out_channels, 1)
        self.proj_w = DurationPredictor(self.hidden_channels + gin_channels, filter_channels_dp, kernel_size, p_dropout)

    def forward(self, x, x_lengths, g=None):
        # x = self.emb(x) * math.sqrt(self.hidden_channels)  # [b, t, h]
        # x = torch.transpose(x, 1, -1)  # [b, h, t]
        x_mask = torch.unsqueeze(commons.sequence_mask(x_lengths, x.size(1)), 1).to(x.dtype)

        x = self.encoder(x, x_lengths).transpose(1,2)

        if g is not None:
            g_exp = g.expand(-1, -1, x.size(-1))
            # print(f"Dimension of input in Text Encoder: x.shape: {x.shape}; g: {g.shape}, g_exp: {g_exp.shape}")
            x_dp = torch.cat([torch.detach(x), g_exp], 1)
        else:
            x_dp = torch.detach(x)
        x_m = self.proj_m(x) * x_mask
        if not self.mean_only:
            x_logs = self.proj_s(x) * x_mask
        else:
            x_logs = torch.zeros_like(x_m)

        # print(f"Dimension of input in Text Encoder before DP: {x_dp.shape}")

        logw = self.proj_w(x_dp, x_mask)
        return x_m, x_logs, logw, x_mask


class FlowDecoder(nn.Module):
    def __init__(
        self,
        in_channels,
        hidden_channels,
        kernel_size,
        dilation_rate,
        n_blocks,
        n_layers,
        p_dropout=0.0,
        n_split=4,
        n_sqz=2,
        sigmoid_scale=False,
        gin_channels=0,
    ):
        """Flow-based decoder model

        Args:
            in_channels (int): Number of incoming channels
            hidden_channels (int): Number of hidden channels
            kernel_size (int): Kernel Size for convolutions in coupling blocks
            dilation_rate (float): Dilation Rate to define dilation in convolutions of coupling block
            n_blocks (int): Number of coupling blocks
            n_layers (int): Number of layers in CNN of the coupling blocks
            p_dropout (float, optional): Dropout probability for CNN in coupling blocks. Defaults to 0..
            n_split (int, optional): Number of splits for the 1x1 convolution for flows in the decoder. Defaults to 4.
            n_sqz (int, optional): Squeeze. Defaults to 1.
            sigmoid_scale (bool, optional): Boolean to define if log probs in coupling layers should be rescaled using sigmoid. Defaults to False.
            gin_channels (int, optional): Number of speaker embedding channels. Defaults to 0.
        """
        super().__init__()

        self.in_channels = in_channels
        self.hidden_channels = hidden_channels
        self.kernel_size = kernel_size
        self.dilation_rate = dilation_rate
        self.n_blocks = n_blocks
        self.n_layers = n_layers
        self.p_dropout = p_dropout
        self.n_split = n_split
        self.n_sqz = n_sqz
        self.sigmoid_scale = sigmoid_scale
        self.gin_channels = gin_channels

        self.flows = nn.ModuleList()

        for b in range(n_blocks):
            self.flows.append(modules.ActNorm(channels=in_channels * n_sqz))
            self.flows.append(modules.InvConvNear(channels=in_channels * n_sqz, n_split=n_split))
            self.flows.append(
                attentions.CouplingBlock(
                    in_channels * n_sqz,
                    hidden_channels,
                    kernel_size=kernel_size,
                    dilation_rate=dilation_rate,
                    n_layers=n_layers,
                    gin_channels=gin_channels,
                    p_dropout=p_dropout,
                    sigmoid_scale=sigmoid_scale,
                )
            )

    def forward(self, x, x_mask, g=None, reverse=False):
        if not reverse:
            flows = self.flows
            logdet_tot = 0
        else:
            flows = reversed(self.flows)
            logdet_tot = None

        if self.n_sqz > 1:
            x, x_mask = commons.channel_squeeze(x, x_mask, self.n_sqz)
        for f in flows:
            if not reverse:
                x, logdet = f(x, x_mask, g=g, reverse=reverse)
                logdet_tot += logdet
            else:
                x, logdet = f(x, x_mask, g=g, reverse=reverse)
        if self.n_sqz > 1:
            x, x_mask = commons.channel_unsqueeze(x, x_mask, self.n_sqz)
        return x, logdet_tot

    def store_inverse(self):
        for f in self.flows:
            f.store_inverse()

class Model(nn.Module):
    """
    Flow-based TTS model based on GlowTTS Structure
    Following the definition from https://arxiv.org/abs/2005.11129
    and code from https://github.com/jaywalnut310/glow-tts
    """

    def __init__(
        self,
        n_vocab: int,
        hidden_channels: int,
        filter_channels_dp: int,
        out_channels: int,
        encoder_config: NarEncoderConfig,
        kernel_size: int = 3,
        p_dropout: float = 0.0,
        n_blocks_dec: int = 12,
        kernel_size_dec: int = 5,
        dilation_rate: int = 5,
        n_block_layers: int = 4,
        p_dropout_dec: float = 0.0,
        n_speakers: int = 0,
        gin_channels: int = 0,
        n_split: int = 4,
        n_sqz: int = 1,
        sigmoid_scale: bool = False,
        mean_only: bool = False,
        hidden_channels_dec: int = None,
        **kwargs,
    ):
        """_summary_

        Args:
            n_vocab (int): vocabulary size
            hidden_channels (int): Number of hidden channels in encoder
            filter_channels (int): Number of filter channels in encoder
            filter_channels_dp (int): Number of filter channels in decoder
            out_channels (int): Number of channels in the output
            kernel_size (int, optional): Size of kernels in the encoder. Defaults to 3.
            n_heads (int, optional): Number of heads in the Multi-Head Attention of the encoder. Defaults to 2.
            n_layers_enc (int, optional): Number of layers in the encoder. Defaults to 6.
            p_dropout (_type_, optional): Dropout probability in the encoder. Defaults to 0..
            n_blocks_dec (int, optional): Number of coupling blocks in the decoder. Defaults to 12.
            kernel_size_dec (int, optional): Kernel size in the decoder. Defaults to 5.
            dilation_rate (int, optional): Dilation rate for CNNs of coupling blocks in decoder. Defaults to 5.
            n_block_layers (int, optional): Number of layers in the CNN of the coupling blocks in decoder. Defaults to 4.
            p_dropout_dec (_type_, optional): Dropout probability in the decoder. Defaults to 0..
            n_speakers (int, optional): Number of speakers. Defaults to 0.
            gin_channels (int, optional): Number of speaker embedding channels. Defaults to 0.
            n_split (int, optional): Number of splits for the 1x1 convolution for flows in the decoder. Defaults to 4.
            n_sqz (int, optional): Squeeze. Defaults to 1.
            sigmoid_scale (bool, optional): Boolean to define if log probs in coupling layers should be rescaled using sigmoid. Defaults to False.
            window_size (int, optional): Window size  in Multi-Head Self-Attention for encoder. Defaults to None.
            block_length (_type_, optional): Block length for optional block masking in Multi-Head Attention for encoder. Defaults to None.
            mean_only (bool, optional): Boolean to only project text encodings to mean values instead of mean and std. Defaults to False.
            hidden_channels_enc (int, optional): Number of hidden channels in encoder. Defaults to hidden_channels.
            hidden_channels_dec (_type_, optional): Number of hidden channels in decodder. Defaults to hidden_channels.
            prenet (bool, optional): Boolean to add ConvReluNorm prenet before encoder . Defaults to False.
        """
        super().__init__()
        self.n_vocab = n_vocab
        self.hidden_channels = hidden_channels
        self.filter_channels_dp = filter_channels_dp
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.p_dropout = p_dropout
        self.n_blocks_dec = n_blocks_dec
        self.kernel_size_dec = kernel_size_dec
        self.dilation_rate = dilation_rate
        self.n_block_layers = n_block_layers
        self.p_dropout_dec = p_dropout_dec
        self.n_speakers = n_speakers
        self.gin_channels = gin_channels
        self.n_split = n_split
        self.n_sqz = n_sqz
        self.sigmoid_scale = sigmoid_scale
        self.mean_only = mean_only
        self.hidden_channels_dec = hidden_channels_dec

        fe_config = DbMelFeatureExtractionConfig.from_dict(kwargs["fe_config"])
        self.feature_extraction = DbMelFeatureExtraction(config=fe_config)

        self.encoder = TextEncoder(
            encoder_config,
            out_channels,
            filter_channels_dp,
            kernel_size,
            p_dropout,
            mean_only=mean_only,
            gin_channels=gin_channels
        )

        self.decoder = FlowDecoder(
            out_channels,
            hidden_channels_dec or hidden_channels,
            kernel_size_dec,
            dilation_rate,
            n_blocks_dec,
            n_block_layers,
            p_dropout=p_dropout_dec,
            n_split=n_split,
            n_sqz=n_sqz,
            sigmoid_scale=sigmoid_scale,
            gin_channels=gin_channels,
        )

        if n_speakers > 1:
            self.emb_g = nn.Embedding(n_speakers, gin_channels)
            nn.init.uniform_(self.emb_g.weight, -0.1, 0.1)

    def forward(
        self, x, x_lengths, raw_audio=None, raw_audio_lengths=None, g=None, gen=False, noise_scale=1.0, length_scale=1.0
    ):
        if not gen:
            with torch.no_grad():
                squeezed_audio = torch.squeeze(raw_audio)
                y, y_lengths = self.feature_extraction(
                    squeezed_audio, raw_audio_lengths
                )  # [B, T, F]
                y = y.transpose(1, 2)  # [B, F, T]
        else:
            y, y_lengths = (None, None)

        if g is not None:
            g = nn.functional.normalize(self.emb_g(g.squeeze(-1))).unsqueeze(-1)
        x_m, x_logs, logw, x_mask = self.encoder(x, x_lengths, g=g)  # mean, std logs, duration logs, mask

        if gen:  # durations from dp only used during generation
            w = torch.exp(logw) * x_mask * length_scale  # durations
            w_ceil = torch.ceil(w)  # durations ceiled
            y_lengths = torch.clamp_min(torch.sum(w_ceil, [1, 2]), 1).long()
            y_max_length = None
        else:
            y_max_length = y.size(2)

        y, y_lengths, y_max_length = self.preprocess(y, y_lengths, y_max_length)
        z_mask = torch.unsqueeze(commons.sequence_mask(y_lengths, y_max_length), 1).to(x_mask.dtype)
        attn_mask = torch.unsqueeze(x_mask, -1) * torch.unsqueeze(z_mask, 2)

        if gen:
            attn = commons.generate_path(w_ceil.squeeze(1), attn_mask.squeeze(1)).unsqueeze(1).to(w_ceil.dtype)
            z_m = torch.matmul(attn.squeeze(1).transpose(1, 2), x_m.transpose(1, 2)).transpose(1, 2)
            z_logs = torch.matmul(attn.squeeze(1).transpose(1, 2), x_logs.transpose(1, 2)).transpose(1, 2)
            logw_ = torch.log(1e-8 + torch.sum(attn, -1)) * x_mask

            z = (z_m + torch.exp(z_logs) * torch.randn_like(z_m) * noise_scale) * z_mask
            y, logdet = self.decoder(z, z_mask, g=g, reverse=True)
            return (y, z_m, z_logs, logdet, z_mask, y_lengths), (x_m, x_logs, x_mask), (attn, logw, logw_)
        else:
            z, logdet = self.decoder(y, z_mask, g=g, reverse=False)
            with torch.no_grad():
                x_s_sq_r = torch.exp(-2 * x_logs)
                logp1 = torch.sum(-0.5 * math.log(2 * math.pi) - x_logs, [1]).unsqueeze(-1)  # [b, t, 1]
                logp2 = torch.matmul(x_s_sq_r.transpose(1, 2), -0.5 * (z**2))  # [b, t, d] x [b, d, t'] = [b, t, t']
                logp3 = torch.matmul((x_m * x_s_sq_r).transpose(1, 2), z)  # [b, t, d] x [b, d, t'] = [b, t, t']
                logp4 = torch.sum(-0.5 * (x_m**2) * x_s_sq_r, [1]).unsqueeze(-1)  # [b, t, 1]
                logp = logp1 + logp2 + logp3 + logp4  # [b, t, t']

                attn = maximum_path(logp, attn_mask.squeeze(1)).unsqueeze(1).detach()
                # embed()

            z_m = torch.matmul(attn.squeeze(1).transpose(1, 2), x_m.transpose(1, 2)).transpose(
                1, 2
            )  # [b, t', t], [b, t, d] -> [b, d, t']
            z_logs = torch.matmul(attn.squeeze(1).transpose(1, 2), x_logs.transpose(1, 2)).transpose(
                1, 2
            )  # [b, t', t], [b, t, d] -> [b, d, t']

            logw_ = torch.log(1e-8 + torch.sum(attn, -1)) * x_mask
            return (z, z_m, z_logs, logdet, z_mask), (x_m, x_logs, x_mask), (attn, logw, logw_)

    def preprocess(self, y, y_lengths, y_max_length):
        if y_max_length is not None:
            y_max_length = (y_max_length // self.n_sqz) * self.n_sqz
            y = y[:, :, :y_max_length]
        y_lengths = (y_lengths // self.n_sqz) * self.n_sqz
        return y, y_lengths, y_max_length

    def store_inverse(self):
        self.decoder.store_inverse()


def train_step(*, model: Model, data, run_ctx, **kwargs):
    tags = data["seq_tag"]
    audio_features = data["audio_features"]  # [B, T, F]
    # audio_features = audio_features.transpose(1, 2) # [B, F, T] necessary because glowTTS expects the channels to be in the 2nd dimension
    audio_features_len = data["audio_features:size1"]  # [B]

    # perform local length sorting for more efficient packing
    audio_features_len, indices = torch.sort(audio_features_len, descending=True)

    audio_features = audio_features[indices, :, :]
    phonemes = data["phonemes"][indices, :]  # [B, T] (sparse)
    phonemes_len = data["phonemes:size1"][indices]  # [B, T]
    speaker_labels = data["speaker_labels"][indices, :]  # [B, 1] (sparse)
    tags = list(np.array(tags)[indices.detach().cpu().numpy()])

    # print(f"phoneme shape: {phonemes.shape}")
    # print(f"phoneme length: {phonemes_len}")
    # print(f"audio_feature shape: {audio_features.shape}")
    # print(f"audio_feature length: {audio_features_len}")
    (z, z_m, z_logs, logdet, z_mask), (x_m, x_logs, x_mask), (attn, logw, logw_) = model(
        phonemes, phonemes_len, audio_features, audio_features_len, speaker_labels
    )
    # embed()

    l_mle = commons.mle_loss(z, z_m, z_logs, logdet, z_mask)
    l_dp = commons.duration_loss(logw, logw_, phonemes_len)

    run_ctx.mark_as_loss(name="mle", loss=l_mle)
    run_ctx.mark_as_loss(name="dp", loss=l_dp)


############# FORWARD STUFF ################
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

def forward_init_hook_spectrograms(run_ctx, **kwargs):
    run_ctx.hdf_writer = SimpleHDFWriter("output.hdf", dim=80, ndim=2)
    run_ctx.pool = multiprocessing.Pool(8)

def forward_finish_hook_spectrograms(run_ctx, **kwargs):
    run_ctx.hdf_writer.close()

def forward_init_hook_durations(run_ctx, **kwargs):
    run_ctx.hdf_writer = SimpleHDFWriter("output.hdf", dim=80, ndim=1)
    run_ctx.pool = multiprocessing.Pool(8)

def forward_finish_hook_durations(run_ctx, **kwargs):
    run_ctx.hdf_writer.close()


def forward_init_hook(run_ctx, **kwargs):
    import json
    import utils
    from utils import AttrDict
    from inference import load_checkpoint
    from generator import UnivNet as Generator
    import numpy as np

    with open("/u/lukas.rilling/experiments/glow_tts_asr_v2/config_univ.json") as f:
        data = f.read()

    json_config = json.loads(data)
    h = AttrDict(json_config)

    generator = Generator(h).to(run_ctx.device)

    state_dict_g = load_checkpoint("/work/asr3/rossenbach/rilling/vocoder/univnet/glow_finetuning/g_01080000", run_ctx.device)
    generator.load_state_dict(state_dict_g["generator"])

    run_ctx.generator = generator


def forward_finish_hook(run_ctx, **kwargs):
    pass


MAX_WAV_VALUE = 32768.0


def forward_step(*, model: Model, data, run_ctx, **kwargs):
    phonemes = data["phonemes"]  # [B, N] (sparse)
    phonemes_len = data["phonemes:size1"]  # [B]
    speaker_labels = data["speaker_labels"]  # [B, 1] (sparse)
    audio_features = data["audio_features"]

    tags = data["seq_tag"]

    (log_mels, z_m, z_logs, logdet, z_mask, y_lengths), (x_m, x_logs, x_mask), (attn, logw, logw_) = model(
        phonemes,
        phonemes_len,
        g=speaker_labels,
        gen=True,
        noise_scale=kwargs["noise_scale"],
        length_scale=kwargs["length_scale"],
    )

    noise = torch.randn([1, 64, log_mels.shape[-1]]).to(device=log_mels.device)
    audios = run_ctx.generator.forward(noise, log_mels)
    audios = audios * MAX_WAV_VALUE
    audios = audios.cpu().numpy().astype("int16")

    # mels_gt = audio_features.transpose(1, 2)
    # noise = torch.randn([1, 64, mels_gt.shape[-1]]).to(device=mels_gt.device)
    # audios_gt = run_ctx.generator.forward(noise, mels_gt)
    # audios_gt = audios_gt * MAX_WAV_VALUE
    # audios_gt = audios_gt.cpu().numpy().astype("int16")

    if not os.path.exists("/var/tmp/lukas.rilling/"):
        os.makedirs("/var/tmp/lukas.rilling/")
    if not os.path.exists("/var/tmp/lukas.rilling/out"):
        os.makedirs("/var/tmp/lukas.rilling/out/", exist_ok=True)
    for audio, tag in zip(audios, tags):
        soundfile.write(f"/var/tmp/lukas.rilling/out/" + tag.replace("/", "_") + ".wav", audio[0], 16000)
        # soundfile.write(f"/var/tmp/lukas.rilling/out/" + tag.replace("/", "_") + "_gt.wav", audio_gt[0], 16000)


def forward_step_spectrograms(*, model: Model, data, run_ctx, **kwargs):
    tags = data["seq_tag"]
    audio_features = data["audio_features"]  # [B, T, F]
    audio_features = audio_features.transpose(
        1, 2
    )  # [B, F, T] necessary because glowTTS expects the channels to be in the 2nd dimension
    audio_features_len = data["audio_features:size1"]  # [B]

    # perform local length sorting for more efficient packing
    audio_features_len, indices = torch.sort(audio_features_len, descending=True)

    audio_features = audio_features[indices, :, :]
    phonemes = data["phonemes"][indices, :]  # [B, T] (sparse)
    phonemes_len = data["phonemes:size1"][indices]  # [B, T]
    speaker_labels = data["speaker_labels"][indices, :]  # [B, 1] (sparse)
    tags = list(np.array(tags)[indices.detach().cpu().numpy()])

    (y, z_m, z_logs, logdet, z_mask, y_lengths), (x_m, x_logs, x_mask), (attn, logw, logw_) = model(
        phonemes, phonemes_len, g=speaker_labels, gen=True, noise_scale=kwargs["noise_scale"], length_scale=kwargs["length_scale"]
    ) 
    spectograms = y.transpose(2, 1).detach().cpu().numpy()  # [B, T, F]

    run_ctx.hdf_writer.insert_batch(spectograms, y_lengths.detach().cpu().numpy(), tags)


def forward_step_durations(*, model: Model, data, run_ctx, **kwargs):
    """Forward Step to output durations in HDF file
    Currently unused due to the name. Only "forward_step" is used in ReturnnForwardJob.
    Rename to use it as the forward step function.

    :param Model model: _description_
    :param _type_ data: _description_
    :param _type_ run_ctx: _description_
    """
    tags = data["seq_tag"]
    audio_features = data["audio_features"]  # [B, T, F]
    audio_features = audio_features.transpose(
        1, 2
    )  # [B, F, T] necessary because glowTTS expects the channels to be in the 2nd dimension
    audio_features_len = data["audio_features:size1"]  # [B]

    # perform local length sorting for more efficient packing
    audio_features_len, indices = torch.sort(audio_features_len, descending=True)

    audio_features = audio_features[indices, :, :]
    phonemes = data["phonemes"][indices, :]  # [B, T] (sparse)
    phonemes_len = data["phonemes:size1"][indices]  # [B, T]
    speaker_labels = data["speaker_labels"][indices, :]  # [B, 1] (sparse)
    tags = list(np.array(tags)[indices.detach().cpu().numpy()])

    # embed()
    (y, z_m, z_logs, logdet, z_mask, y_lengths), (x_m, x_logs, x_mask), (attn, logw, logw_) = model(
        phonemes, phonemes_len, g=speaker_labels, gen=True
    ) 
    # embed()
    numpy_logprobs = logw.detach().cpu().numpy()

    durations_with_pad = np.round(np.exp(numpy_logprobs) * x_mask.detach().cpu().numpy())
    durations = durations_with_pad.squeeze(1)
    for tag, duration, feat_len, phon_len in zip(tags, durations, audio_features_len, phonemes_len):
        # d = duration[:phon_len]
        # total_sum = np.sum(duration)
        # assert total_sum == feat_len
        
        # assert len(d) == phon_len
        run_ctx.hdf_writer.insert_batch(np.asarray([duration[:phon_len]]), [phon_len.cpu().numpy()], [tag])
