"""
Prototype greedy AED decoder
"""
from dataclasses import dataclass
import time
import torch
import numpy



@dataclass
class DecoderConfig:
    returnn_vocab: str


@dataclass
class ExtraConfig:
    # used for RTF logging
    print_rtf: bool = True
    sample_rate: int = 16000

    # Hypothesis logging
    print_hypothesis: bool = True


def forward_init_hook(run_ctx, **kwargs):
    # we are storing durations, but call it output.hdf to match
    # the default output of the ReturnnForwardJob
    config = DecoderConfig(**kwargs["config"])
    extra_config_dict = kwargs.get("extra_config", {})
    extra_config = ExtraConfig(**extra_config_dict)

    run_ctx.recognition_file = open("search_out.py", "wt")
    run_ctx.recognition_file.write("{\n")

    from returnn.datasets.util.vocabulary import Vocabulary
    vocab = Vocabulary.create_vocab(
        vocab_file=config.returnn_vocab, unknown_label=None)
    run_ctx.labels = vocab.labels

    run_ctx.print_rtf = extra_config.print_rtf
    if run_ctx.print_rtf:
        run_ctx.running_audio_len_s = 0
        run_ctx.total_time = 0

    run_ctx.print_hypothesis = extra_config.print_hypothesis


def forward_finish_hook(run_ctx, **kwargs):
    run_ctx.recognition_file.write("}\n")
    run_ctx.recognition_file.close()

    print("Total-time: %.2f, Batch-RTF: %.3f" % (run_ctx.total_time, run_ctx.total_time / run_ctx.running_audio_len_s))

def forward_step(*, model, data, run_ctx, **kwargs):
    raw_audio = data["raw_audio"]  # [B, T', F]
    raw_audio_len = data["raw_audio:size1"]  # [B]

    audio_len_batch = torch.sum(raw_audio_len).detach().cpu().numpy() / 16000

    if run_ctx.print_rtf:
        run_ctx.running_audio_len_s += audio_len_batch
        am_start = time.time()

    label_stack, total_scores = model(
        raw_audio=raw_audio,
        raw_audio_len=raw_audio_len,
        bpe_labels=None,
        do_search=True,
    )

    tags = data["seq_tag"]

    total_scores = total_scores.cpu().detach().numpy()
    label_stack = numpy.transpose(numpy.asarray(label_stack))[0]
    # print(label_stack)
    # print(total_scores)

    if run_ctx.print_rtf:
        am_time = time.time() - am_start
        run_ctx.total_time += am_time
        print("Batch-time: %.2f, Batch-RTF: %.3f" % (am_time, am_time / audio_len_batch))

    # hypothesis = run_ctx.ctc_decoder(logprobs.cpu(), audio_features_len.cpu())
    for hyp, tag in zip (label_stack, tags):
        hyp_ = []
        for i in hyp:
            if i == 0:
                break
            else:
                hyp_.append(i)
        sequence = " ".join([run_ctx.labels[i] for i in hyp_])
        text = sequence.replace("@@ ", "")
        print(text)
        run_ctx.recognition_file.write("%s: %s,\n" % (repr(tag), repr(text)))