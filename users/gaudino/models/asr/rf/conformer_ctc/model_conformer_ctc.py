from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union, Tuple, Sequence, List, Collection, Dict
import tree
import math
import numpy as np
import torch
import hashlib
import contextlib
import functools

from returnn.tensor import Tensor, Dim, single_step_dim
import returnn.frontend as rf
from returnn.frontend.tensor_array import TensorArray
from returnn.frontend.encoder.conformer import ConformerEncoder, ConformerConvSubsampleV2, ConformerConvSubsample

from i6_experiments.users.gaudino.model_interfaces.supports_label_scorer_torch import (
    RFModelWithMakeLabelScorer,
)

from i6_experiments.users.gaudino.experiments.rf_conformer_att_2023.librispeech_960.trafo_lm import (
    trafo_lm_kazuki_import,
)

from i6_experiments.users.gaudino.models.asr.rf.nn_lm.lm_import_2023_11_09 import (
    Trafo_LM_Model,
)
from i6_experiments.users.gaudino.models.asr.rf.nn_lm.lm_import_2023_09_03 import (
    LSTM_LM_Model,
    # MakeModel,
)

if TYPE_CHECKING:
    from i6_experiments.users.zeyer.model_interfaces import ModelDef, RecogDef, TrainDef
    from i6_experiments.users.zeyer.model_with_checkpoints import (
        ModelWithCheckpoints,
        ModelWithCheckpoint,
    )

_log_mel_feature_dim = 80


class MakeModel:
    """for import"""

    def __init__(
        self,
        in_dim: int,
        target_dim: int,
        *,
        eos_label: int = 0,
        num_enc_layers: int = 12,
    ):
        self.in_dim = in_dim
        self.target_dim = target_dim
        self.eos_label = eos_label
        self.num_enc_layers = num_enc_layers

    def __call__(self) -> Model:
        from returnn.datasets.util.vocabulary import Vocabulary

        in_dim = Dim(name="in", dimension=self.in_dim, kind=Dim.Types.Feature)
        target_dim = Dim(
            name="target", dimension=self.target_dim, kind=Dim.Types.Feature
        )
        target_dim.vocab = Vocabulary.create_vocab_from_labels(
            [str(i) for i in range(target_dim.dimension)], eos_label=self.eos_label
        )

        return self.make_model(in_dim, target_dim, num_enc_layers=self.num_enc_layers)

    @classmethod
    def make_model(
        cls,
        in_dim: Dim,
        target_dim: Dim,
        *,
        num_enc_layers: int = 12,
        pos_emb_dropout: float = 0.0,
        lm_opts: Optional[Dict[str, Any]] = None,
        **extra,
    ) -> Model:
        """make"""

        lm = None
        if lm_opts:
            assert isinstance(lm_opts, dict)
            lm_opts = lm_opts.copy()
            cls_name = lm_opts.pop("class")
            assert cls_name == "Trafo_LM_Model" or cls_name == "LSTM_LM_Model"
            lm_opts.pop("vocab_dim", None)  # will just overwrite

            if cls_name == "Trafo_LM_Model":
                lm = Trafo_LM_Model(target_dim, target_dim, **lm_opts)

            elif cls_name == "LSTM_LM_Model":
                lm = LSTM_LM_Model(target_dim, target_dim, **lm_opts)

        return Model(
            in_dim,
            num_enc_layers=num_enc_layers,
            enc_model_dim=Dim(name="enc", dimension=512, kind=Dim.Types.Feature),
            enc_ff_dim=Dim(name="enc-ff", dimension=2048, kind=Dim.Types.Feature),
            enc_att_num_heads=8,
            enc_conformer_layer_opts=dict(
                conv_norm_opts=dict(use_mask=True),
                self_att_opts=dict(
                    # Shawn et al 2018 style, old RETURNN way.
                    with_bias=False,
                    with_linear_pos=False,
                    with_pos_bias=False,
                    learnable_pos_emb=True,
                    separate_pos_emb_per_head=False,
                    pos_emb_dropout=pos_emb_dropout,
                ),
                ff_activation=lambda x: rf.relu(x) ** 2.0,
            ),
            target_dim=target_dim,
            blank_idx=target_dim.dimension,
            bos_idx=_get_bos_idx(target_dim),
            eos_idx=_get_eos_idx(target_dim),
            language_model=lm,
            **extra,
        )

class MakeModelV2:
    """for import with i6 models settings"""

    def __init__(
        self,
        in_dim: int,
        target_dim: int,
        *,
        eos_label: int = 0,
        num_enc_layers: int = 12,
    ):
        self.in_dim = in_dim
        self.target_dim = target_dim
        self.eos_label = eos_label
        self.num_enc_layers = num_enc_layers

    def __call__(self) -> Model:
        from returnn.datasets.util.vocabulary import Vocabulary

        in_dim = Dim(name="in", dimension=self.in_dim, kind=Dim.Types.Feature)
        target_dim = Dim(
            name="target", dimension=self.target_dim, kind=Dim.Types.Feature
        )
        target_dim.vocab = Vocabulary.create_vocab_from_labels(
            [str(i) for i in range(target_dim.dimension)], eos_label=self.eos_label
        )

        return self.make_model(in_dim, target_dim, num_enc_layers=self.num_enc_layers)

    @classmethod
    def make_model(
        cls,
        in_dim: Dim,
        target_dim: Dim,
        *,
        num_enc_layers: int = 12,
        pos_emb_dropout: float = 0.0,
        language_model: Optional[Dict[str, Any]] = None,
        **extra,
    ) -> Model:
        """make"""
        lm = None
        if language_model:
            assert isinstance(language_model, dict)
            language_model = language_model.copy()
            cls_name = language_model.pop("class")
            assert cls_name == "TransformerDecoder"
            language_model.pop("vocab_dim", None)  # will just overwrite

            from i6_experiments.users.gaudino.experiments.rf_conformer_att_2023.librispeech_960.trafo_lm.trafo_lm import (
                trafo_lm,
            )

            lm = trafo_lm.MakeModel(vocab_dim=target_dim, **language_model)()
            lm = (lm, functools.partial(trafo_lm.make_label_scorer_torch, model=lm))

        return Model(
            in_dim,
            num_enc_layers=num_enc_layers,
            enc_model_dim=Dim(name="enc", dimension=512, kind=Dim.Types.Feature),
            enc_ff_dim=Dim(name="enc-ff", dimension=2048, kind=Dim.Types.Feature),
            enc_att_num_heads=8,
            enc_conformer_layer_opts=dict(
                conv_norm = rf.LayerNorm,
                # conv_norm_opts=dict(
                #     in_dim=
                # ),  # Changed below
                self_att=rf.SelfAttention,
                self_att_opts=dict(
                    with_bias=True,  # Changed: with_bias=True
                    # with_linear_pos=False,
                    # with_pos_bias=False,
                    # learnable_pos_emb=False,  # Changed: learnable_pos_emb=False
                    # separate_pos_emb_per_head=False,
                    # pos_emb_dropout=pos_emb_dropout,
                ),
                ff_activation=rf.silu,  # Changed: rf.silu
                conv_kernel_size=31,  # Changed: conv_kernel_size=31
            ),
            enc_input_layer=ConformerConvSubsampleV2(
                in_dim,
                out_dims=[
                    Dim(32, name="conv1"),
                    Dim(64, name="conv2"),
                    Dim(64, name="conv3"),
                    Dim(32, name="conv4"),  # Changed: Dim(64, name="conv4")
                ],
                filter_sizes=[(3, 3), (3, 3), (3, 3), (3, 3)],  # Changed
                activation_times=[False, True, False, True],  # Changed
                pool_sizes=[(1, 1), (3, 1), (1, 1), (2, 1)],  # Changed
                pool_strides=[(1, 1), (2, 1), (1, 1), (2, 1)],  # Changed !!! different from rnnt
                strides=[(1, 1), (1, 1), (1, 1), (1, 1)],  # Changed
                padding="same",  # Changed: padding="valid"
                pool_padding="valid",  # Changed
                swap_merge_dim_order=True,  # Changed
                # Note: uses relu activation by default
            ),
            enc_use_input_proj_bias=True,  # Changed: enc_use_input_proj_bias=True
            target_dim=target_dim,
            blank_idx=target_dim.dimension,
            bos_idx=_get_bos_idx(target_dim),
            eos_idx=_get_eos_idx(target_dim),
            language_model=lm,
            use_i6_models_feat_ext = True, # Changed
            **extra,
        )


class Model(rf.Module):
    """Model definition"""

    def __init__(
        self,
        in_dim: Dim,
        *,
        num_enc_layers: int = 12,
        target_dim: Dim,
        # wb_target_dim: Optional[Dim] = None,
        blank_idx: int,
        eos_idx: int,
        bos_idx: int,
        enc_aux_logits: Sequence[int] = (),  # layers
        enc_model_dim: Dim = Dim(name="enc", dimension=512),
        enc_ff_dim: Dim = Dim(name="enc-ff", dimension=2048),
        enc_att_num_heads: int = 4,
        enc_conformer_layer_opts: Optional[Dict[str, Any]] = None,
        enc_input_layer: Optional[ConformerConvSubsampleV2] = None,
        # enc_key_total_dim: Dim = Dim(name="enc_key_total_dim", dimension=1024),
        # att_num_heads: Dim = Dim(name="att_num_heads", dimension=1),
        # att_dropout: float = 0.1,
        enc_dropout: float = 0.1,
        enc_att_dropout: float = 0.1,
        l2: float = 0.0001,
        language_model: Optional[RFModelWithMakeLabelScorer] = None,
        # joiner_dim: int = 640,
        enc_use_input_proj_bias: bool = False,
        use_i6_models_feat_ext: bool = False,
        feat_ext_opts: Optional[Dict[str, Any]] = None,
    ):
        super(Model, self).__init__()

        from returnn.config import get_global_config

        config = get_global_config(return_empty_if_none=True)

        self.mel_normalization = config.typed_value("mel_normalization_ted2", True)
        self.use_specaugment = config.typed_value("use_specaugment", True)
        self.conv_2nd_stride = config.typed_value("conv_2nd_stride", 3)
        self.final_ctc_name = config.typed_value("final_ctc_name", "enc_aux_logits_12")
        self.gauss_window_size = config.typed_value("gauss_window_size", 0)
        self.gauss_std = config.typed_value("gauss_std", 0.0)

        self.use_i6_models_feat_ext = use_i6_models_feat_ext
        if self.use_i6_models_feat_ext:
            from i6_models.primitives.feature_extraction import (
                LogMelFeatureExtractionV1,
                LogMelFeatureExtractionV1Config,
            )

            mel_config = LogMelFeatureExtractionV1Config(
                sample_rate=16000,
                win_size=0.025,
                hop_size=0.01,
                f_min=60,
                f_max=7600,
                min_amp=1e-10,
                num_filters=80,
                center=False,
                **(feat_ext_opts or {}),
            )
            self.feature_extraction = LogMelFeatureExtractionV1(cfg=mel_config)

        # self.feat_ext_opts = feat_ext_opts

        self.in_dim = in_dim
        self.enc_model_dim = enc_model_dim

        if enc_input_layer is None:
            enc_input_layer = ConformerConvSubsample(
                in_dim,
                out_dims=[
                    Dim(32, name="conv1"),
                    Dim(64, name="conv2"),
                    Dim(64, name="conv3"),
                ],
                filter_sizes=[(3, 3), (3, 3), (3, 3)],
                pool_sizes=[(1, 2)],
                strides=[(1, 1), (self.conv_2nd_stride, 1), (2, 1)],
            )

        self.encoder = ConformerEncoder(
            in_dim,
            enc_model_dim,
            ff_dim=enc_ff_dim,
            input_layer=enc_input_layer,
            encoder_layer_opts=enc_conformer_layer_opts,
            num_layers=num_enc_layers,
            num_heads=enc_att_num_heads,
            dropout=enc_dropout,
            att_dropout=enc_att_dropout,
        )

        self.enc_use_input_proj_bias = enc_use_input_proj_bias

        if self.enc_use_input_proj_bias:
            self.encoder.input_projection = rf.Linear(
                self.encoder.input_layer.out_dim
                if self.encoder.input_layer
                else self.encoder.in_dim,
                self.encoder.out_dim,
                with_bias=True,
            )

        self.target_dim = target_dim
        self.target_dim_w_blank = target_dim + 1
        self.blank_idx = blank_idx
        self.eos_idx = eos_idx
        self.bos_idx = bos_idx  # for non-blank labels; for with-blank labels, we use bos_idx=blank_idx

        if target_dim.vocab and not self.target_dim_w_blank.vocab:
            from returnn.datasets.util.vocabulary import Vocabulary

            # Just assumption for code now, might extend this later.
            assert self.target_dim_w_blank.dimension == target_dim.dimension + 1 and blank_idx == target_dim.dimension
            vocab_labels = list(target_dim.vocab.labels) + ["<blank>"]
            self.target_dim_w_blank.vocab = Vocabulary.create_vocab_from_labels(
                vocab_labels, user_defined_symbols={"<blank>": blank_idx}
            )

        # self.enc_key_total_dim = enc_key_total_dim
        # self.enc_key_per_head_dim = enc_key_total_dim.div_left(att_num_heads)
        # self.att_num_heads = att_num_heads
        # self.att_dropout = att_dropout
        self.dropout_broadcast = rf.dropout_broadcast_default()

        # https://github.com/rwth-i6/returnn-experiments/blob/master/2020-rnn-transducer/configs/base2.conv2l.specaug4a.ctc.devtrain.config

        for p in self.parameters():
            p.weight_decay = l2


        for i in enc_aux_logits:
            setattr(
                self,
                f"enc_aux_logits_{i}",
                rf.Linear(self.encoder.out_dim, self.target_dim_w_blank),
            )

        setattr(self, self.final_ctc_name, rf.Linear(self.encoder.out_dim, self.target_dim_w_blank))

        if self.gauss_window_size > 0.0:
            self.enc_gauss_linear = rf.Linear(2*self.enc_model_dim, enc_model_dim)

        self._specaugment_opts = {
            "steps": config.typed_value("specaugment_steps") or (0, 1000, 2000),
            "max_consecutive_spatial_dims": config.typed_value(
                "specaugment_max_consecutive_spatial_dims"
            )
            or 20,
            "max_consecutive_feature_dims": config.typed_value(
                "specaugment_max_consecutive_feature_dims"
            )
            or (_log_mel_feature_dim // 5),
            "num_spatial_mask_factor": config.typed_value(
                "specaugment_num_spatial_mask_factor"
            )
            or 100,
        }

        self._pretrain_opts: Optional[Dict[str, Any]] = config.typed_value(
            "pretrain_opts"
        )

        self._mixup = None
        if config.typed_value("mixup", None) is not None:
            from i6_experiments.users.zeyer.returnn.models.rf_mixup import (
                Mixup,
                MixupOpts,
            )

            self._mixup = Mixup(
                feature_dim=self.in_dim, opts=MixupOpts(**config.typed_value("mixup"))
            )

        # Note: Even though we have this here, it is not used in loop_step or decode_logits.
        # Instead, it is intended to make a separate label scorer for it.
        self.language_model = None
        if language_model:
            self.language_model = language_model

    def encode(
        self,
        source: Tensor,
        *,
        in_spatial_dim: Dim,
        collected_outputs: Optional[Dict[str, Tensor]] = None,
    ) -> Tuple[Dict[str, Tensor], Dim]:
        """encode, and extend the encoder output for things we need in the decoder"""

        if self.use_i6_models_feat_ext:
            orig_device = source.device
            squeezed_features = torch.squeeze(source.raw_tensor)
            squeezed_features = squeezed_features.to("cpu")
            raw_audio_len = in_spatial_dim.dyn_size_ext.raw_tensor
            audio_features, audio_features_len_raw = self.feature_extraction(
                squeezed_features, raw_audio_len
            )
            audio_features_len = rf.Tensor(
                name="audio-features-len",
                dims=[source.dims[0]],
                raw_tensor=audio_features_len_raw,
                dtype="int32",
            )
            in_spatial_dim = Dim(None, name="in-spatial-dim", dyn_size_ext=audio_features_len)
            source = rf.Tensor(
                name="audio-features",
                dims=[source.dims[0], in_spatial_dim, self.in_dim],
                raw_tensor=audio_features,
                dtype=source.dtype,
            )
            source = rf.copy_to_device(source, orig_device)
        else:
            # log mel filterbank features
            source, in_spatial_dim = rf.audio.log_mel_filterbank_from_raw(
                source,
                in_spatial_dim=in_spatial_dim,
                out_dim=self.in_dim,
                sampling_rate=16_000,
                log_base=math.exp(2.3026),  # almost 10.0 but not exactly...
            )

        if self.mel_normalization:
            ted2_global_mean = rf.Tensor(
                name="ted2_global_mean",
                dims=[source.feature_dim],
                dtype=source.dtype,
                raw_tensor=torch.tensor(
                    np.loadtxt(
                        "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/returnn/dataset/ExtractDatasetMeanStddevJob.UHCZghp269OR/output/mean",
                        dtype="float32",
                    )
                ),
            )
            ted2_global_stddev = rf.Tensor(
                name="ted2_global_stddev",
                dims=[source.feature_dim],
                dtype=source.dtype,
                raw_tensor=torch.tensor(
                    np.loadtxt(
                        "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/returnn/dataset/ExtractDatasetMeanStddevJob.UHCZghp269OR/output/std_dev",
                        dtype="float32",
                    )
                ),
            )

            source = (source - rf.copy_to_device(ted2_global_mean)) / rf.copy_to_device(
                ted2_global_stddev
            )

        if self._mixup:
            source = self._mixup(source, spatial_dim=in_spatial_dim)
        if self.use_specaugment:
            # SpecAugment
            source = rf.audio.specaugment(
                source,
                spatial_dim=in_spatial_dim,
                feature_dim=self.in_dim,
                **self._specaugment_opts,
            )
        # Encoder including convolutional frontend
        with _opt_apply_pretrain_to_encoder(
            self.encoder, collected_outputs, self._pretrain_opts
        ):
            enc, enc_spatial_dim = self.encoder(
                source,
                in_spatial_dim=in_spatial_dim,
                collected_outputs=collected_outputs,
            )

        if self.gauss_window_size > 0:
            enc_raw = enc.raw_tensor # B,T,F
            r_win = self.gauss_window_size // 2

            # Create a 1D Gaussian kernel
            gauss = torch.exp(
                -0.5 * (torch.arange(-r_win, r_win + 1) / self.gauss_std) ** 2
            )

            # Normalize the kernel
            gauss = (gauss / gauss.sum()).to("cuda")

            # pad with window size // 2 on both sides on the time dimension
            data_pad = torch.nn.functional.pad(enc_raw, (0, 0, r_win, r_win))

            # Create a view of the data with a sliding window
            data_unf = data_pad.unfold(1, self.gauss_window_size, 1)
            data_unf = data_unf.permute(0, 1, 3, 2)

            # Apply the Gaussian kernel
            enc_gauss_raw = torch.einsum("btwh, w -> btwh", data_unf, gauss)

            # Sum the weighted values
            enc_gauss_raw = enc_gauss_raw.sum(dim=2)

            enc_gauss = rf.Tensor(
                name="enc_gauss",
                dims=enc.dims,
                dtype=enc.dtype,
                raw_tensor=enc_gauss_raw,
            )
            
            # concat the original data with the weighted data
            enc_w_gauss, _ = rf.concat((enc, self.enc_model_dim), (enc_gauss, self.enc_model_dim))

            enc = self.enc_gauss_linear(enc_w_gauss)

        return (
            dict(enc=enc),
            enc_spatial_dim,
        )

def _get_bos_idx(target_dim: Dim) -> int:
    """for non-blank labels"""
    assert target_dim.vocab
    if target_dim.vocab.bos_label_id is not None:
        bos_idx = target_dim.vocab.bos_label_id
    elif target_dim.vocab.eos_label_id is not None:
        bos_idx = target_dim.vocab.eos_label_id
    elif "<sil>" in target_dim.vocab.user_defined_symbol_ids:
        bos_idx = target_dim.vocab.user_defined_symbol_ids["<sil>"]
    else:
        raise Exception(f"cannot determine bos_idx from vocab {target_dim.vocab}")
    return bos_idx


def _get_eos_idx(target_dim: Dim) -> int:
    """for non-blank labels"""
    assert target_dim.vocab
    if target_dim.vocab.eos_label_id is not None:
        eos_idx = target_dim.vocab.eos_label_id
    else:
        raise Exception(f"cannot determine eos_idx from vocab {target_dim.vocab}")
    return eos_idx


def from_scratch_model_def(*, epoch: int, in_dim: Dim, target_dim: Dim) -> Model:
    """Function is run within RETURNN."""
    from returnn.config import get_global_config

    in_dim, epoch  # noqa
    config = get_global_config()  # noqa
    enc_aux_logits = config.typed_value("aux_loss_layers")
    pos_emb_dropout = config.float("pos_emb_dropout", 0.0)
    # real input is raw audio, internally it does logmel
    in_dim = Dim(name="logmel", dimension=_log_mel_feature_dim, kind=Dim.Types.Feature)
    lm_opts = config.typed_value("external_language_model")
    return MakeModel.make_model(
        in_dim,
        target_dim,
        enc_aux_logits=enc_aux_logits or (),
        pos_emb_dropout=pos_emb_dropout,
        lm_opts=lm_opts,
    )


from_scratch_model_def: ModelDef[Model]
from_scratch_model_def.behavior_version = 16
from_scratch_model_def.backend = "torch"
from_scratch_model_def.batch_size_factor = 160

def from_scratch_model_def_v2(*, epoch: int, in_dim: Dim, target_dim: Dim) -> Model:
    """Function is run within RETURNN."""
    from returnn.config import get_global_config

    in_dim, epoch  # noqa
    config = get_global_config()  # noqa
    enc_aux_logits = config.typed_value("aux_loss_layers")
    pos_emb_dropout = config.float("pos_emb_dropout", 0.0)
    # real input is raw audio, internally it does logmel
    in_dim = Dim(name="logmel", dimension=_log_mel_feature_dim, kind=Dim.Types.Feature)
    lm_opts = config.typed_value("external_language_model")
    return MakeModelV2.make_model(
        in_dim,
        target_dim,
        enc_aux_logits=enc_aux_logits or (),
        pos_emb_dropout=pos_emb_dropout,
        language_model=lm_opts,
    )


from_scratch_model_def_v2: ModelDef[Model]
from_scratch_model_def_v2.behavior_version = 16
from_scratch_model_def_v2.backend = "torch"
from_scratch_model_def_v2.batch_size_factor = 160


def from_scratch_training(
    *,
    model: Model,
    data: rf.Tensor,
    data_spatial_dim: Dim,
    targets: rf.Tensor,
    targets_spatial_dim: Dim,
):
    """Function is run within RETURNN."""
    from returnn.config import get_global_config

    # import for training only, will fail on CPU servers
    # from i6_native_ops import warp_rnnt

    config = get_global_config()  # noqa
    aux_loss_layers = config.typed_value("aux_loss_layers")
    aux_loss_scales = config.typed_value(
        "aux_loss_scales", ([1.0] * len(aux_loss_layers)) if aux_loss_layers else None
    )
    # aed_loss_scale = config.float("aed_loss_scale", 1.0)
    use_normalized_loss = config.bool("use_normalized_loss", True)

    if data.feature_dim and data.feature_dim.dimension == 1:
        data = rf.squeeze(data, axis=data.feature_dim)
    assert not data.feature_dim  # raw audio

    collected_outputs = {}
    enc_args, enc_spatial_dim = model.encode(
        data, in_spatial_dim=data_spatial_dim, collected_outputs=collected_outputs
    )
    if aux_loss_layers:
        for i, layer_idx in enumerate(aux_loss_layers):
            if layer_idx > len(model.encoder.layers):
                continue
            linear = getattr(model, f"enc_aux_logits_{layer_idx}")
            aux_logits = linear(collected_outputs[str(layer_idx - 1)])
            aux_loss = rf.ctc_loss(
                logits=aux_logits,
                targets=targets,
                input_spatial_dim=enc_spatial_dim,
                targets_spatial_dim=targets_spatial_dim,
                blank_index=model.blank_idx,
            )
            aux_loss.mark_as_loss(
                f"ctc_{layer_idx}",
                scale=aux_loss_scales[i],
                custom_inv_norm_factor=targets_spatial_dim.get_size_tensor(),
                use_normalized_loss=use_normalized_loss,
            )
            # Does not work yet. Was commented out before.
            # decoded, decoded_spatial_dim = rf.ctc_greedy_decode(aux_logits, in_spatial_dim=enc_spatial_dim)
            # error = rf.edit_distance(
            #     a=decoded, a_spatial_dim=decoded_spatial_dim, b=targets, b_spatial_dim=targets_spatial_dim
            # )
            # error.mark_as_loss("label", as_error=True, custom_inv_norm_factor=targets_spatial_dim.get_size_tensor())

    aux_logits = model.enc_aux_logits_12(collected_outputs[str(11)])
    aux_loss = rf.ctc_loss(
        logits=aux_logits,
        targets=targets,
        input_spatial_dim=enc_spatial_dim,
        targets_spatial_dim=targets_spatial_dim,
        blank_index=model.blank_idx,
    )
    aux_loss.mark_as_loss(
        f"ctc_12",
        scale=1.0,
        custom_inv_norm_factor=targets_spatial_dim.get_size_tensor(),
        use_normalized_loss=use_normalized_loss,
    )



from_scratch_training: TrainDef[Model]
from_scratch_training.learning_rate_control_error_measure = "dev_score_full_sum"


@contextlib.contextmanager
def _opt_apply_pretrain_to_encoder(
    encoder: ConformerEncoder,
    collected_outputs: Optional[Dict[str, Tensor]],
    pretrain_opts: Optional[Dict[str, Any]],
):
    """Function is run within RETURNN."""
    if not pretrain_opts:
        yield
        return
    step = rf.get_run_ctx().step
    steps: Union[
        Sequence[Tuple[int, Dict[str, Any]]], Dict[int, Dict[str, Any]]
    ] = pretrain_opts["steps"]
    if isinstance(steps, (list, tuple)):
        steps_ = {}
        step_bound = 0
        for step_bound_rel, opts in steps:
            step_bound += step_bound_rel
            steps_[step_bound] = opts
        steps = steps_
    assert isinstance(steps, dict)
    for step_bound, opts in sorted(steps.items()):
        if step < step_bound:
            assert isinstance(opts, dict)
            opts_ = opts.copy()
            # somewhat hacky but that is still the easiest way I can think of, without touching a lot of other code
            pretrain_num_layers = opts_.pop("num_layers")
            assert (
                not opts_
            ), f"unhandled opts: {opts_} in opts {opts} for step bound {step_bound}"
            orig_layers = encoder.layers[:]
            del encoder.layers[pretrain_num_layers:]
            yield
            encoder.layers[:] = orig_layers
            if collected_outputs is not None:
                assert len(collected_outputs) == pretrain_num_layers
                for i in range(pretrain_num_layers, len(orig_layers)):
                    collected_outputs[str(i)] = collected_outputs[
                        str(pretrain_num_layers - 1)
                    ]
            return
    yield
    return
