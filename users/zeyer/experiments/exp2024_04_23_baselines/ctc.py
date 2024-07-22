"""
CTC experiments.
"""

from __future__ import annotations

import copy
import functools
from typing import TYPE_CHECKING, Optional, Union, Tuple, Sequence

from returnn.tensor import Tensor, Dim
import returnn.frontend as rf
from returnn.frontend.tensor_array import TensorArray
from returnn.frontend.encoder.conformer import ConformerEncoder, ConformerConvSubsample
from returnn.frontend.decoder.transformer import TransformerDecoder

from i6_experiments.users.zeyer.model_interfaces import ModelDef, ModelDefWithCfg, RecogDef, TrainDef
from i6_experiments.users.zeyer.returnn.models.rf_layerdrop import SequentialLayerDrop
from i6_experiments.users.zeyer.speed_pert.librosa_config import speed_pert_librosa_config

from .configs import *
from .configs import _get_cfg_lrlin_oclr_by_bs_nep, _batch_size_factor

if TYPE_CHECKING:
    from i6_experiments.common.setups import serialization
    from i6_experiments.users.zeyer.model_with_checkpoints import ModelWithCheckpoints
    from i6_experiments.users.zeyer.datasets.task import Task
    from i6_experiments.users.zeyer.datasets.score_results import RecogOutput


# The model gets raw features (16khz) and does feature extraction internally.
_log_mel_feature_dim = 80

_raw_sample_rate = _batch_size_factor * 100  # bs factor is from 10ms frames to raw samples


def py():
    """Sisyphus entry point"""
    from sisyphus import gs
    from i6_experiments.common.setups import serialization
    from i6_experiments.users.zeyer.datasets.librispeech import get_librispeech_log_mel_stats

    feature_stats = get_librispeech_log_mel_stats(_log_mel_feature_dim)

    train_exp(  # {"dev-clean": 3.12, "dev-other": 7.05, "test-clean": 3.2, "test-other": 7.07}
        f"v6-bhv21-24gb-bf16-bs40k-accgrad2-wd1e_6-lrlin1e_5_450k-bpe10k",
        config_24gb_v6,
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(40_000, 2000),
        },
        enabled=False,
    )

    train_exp(  # {"dev-clean": 3.08, "dev-other": 6.84, "test-clean": 3.28, "test-other": 7.21}
        f"v6-bhv21-24gb-bf16-bs40k-accgrad2-wd1e_6-lrlin1e_5_600k-bpe10k",
        config_24gb_v6,
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(40_000, 2000),
            "learning_rate_piecewise_steps": [600_000, 900_000, 982_000],
        },
        enabled=False,
    )

    train_exp(  # {"dev-clean": 3.1, "dev-other": 6.96, "test-clean": 3.22, "test-other": 7.25}
        f"v6-bhv21-24gb-bf16-bs40k-accgrad2-wd1e_6-lrlin1e_5_600k-featGN-bpe10k",
        config_24gb_v6,
        model_config={"feature_stats": {"mean": feature_stats.mean, "std_dev": feature_stats.std_dev}},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(40_000, 2000),
            "learning_rate_piecewise_steps": [600_000, 900_000, 982_000],
        },
        enabled=False,
    )

    for acc, wd in [
        # (5, 1e-5),
        (5, 1e-3),  # 7.37
        (5, 1e-2),  # 7.31
        # (1, 1e-4),
        (1, 1e-3),  # 6.93
        (1, 1e-2),  # 6.39
        (1, 1e-1),  # 7.34
    ]:
        train_exp(
            f"v6-bhv20-11gb-f32-bs15k-accgrad{acc}"
            f"-mgpu4-pavg100-wd{('%.e'%wd).replace('e-0', 'e_')}"
            f"-lrlin1e_5_295k-bpe10k",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "accum_grad_multiple_step": acc,
                "optimizer.weight_decay": wd,
            },
            enabled=False,
        )

    train_exp(  # 6.82
        f"v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_4-lrlin1e_5_295k-speedpertV2-bpe10k",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
        },
        enabled=False,
    )

    # Comparing vocabs. Note that max_seq_length_default_target=75 always here...
    for vocab in [
        "spm20k",  # 6.12
        "bpe10k",  # 6.57
        "spm10k",  # 6.11
        "spm_bpe10k",  # 6.34
        "spm4k",  # 6.20
        "spm1k",  # 7.34
        "spm_bpe1k",  # 7.39
    ]:
        train_exp(
            f"v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-{vocab}",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            },
            vocab=vocab,
            enabled=False,
        )

    # Comparing vocabs with better settings: feature norm, sampling, no max seq len.
    for vocab, sample, alpha in [
        ("spm20k", "spm", 0.7),  # 6.29
        ("bpe10k", "bpe", 0.01),  # 6.46 (but without featBN,maxSeqLenNone: 6.33)
        ("spm10k", "spm", 0.7),  # 6.31 (but without maxSeqLenNone: 6.29)
        ("spm10k", "bpe", 0.01),  # 6.08
        ("spm_bpe10k", "bpe", 0.01),  # 6.19
        ("spm4k", "spm", 0.7),  # 6.55
        ("spm1k", "spm", 0.7),  # 7.43 (but without spmSample07,featBN,maxSeqLenNone: 7.34)
        # ("spm_bpe1k", ...)
    ]:
        train_exp(
            f"v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenNone"
            f"-wd1e_2-lrlin1e_5_295k-featBN-speedpertV2-{vocab}"
            f"-{sample}Sample{str(alpha).replace('.', '')}",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            model_config={"feature_batch_norm": True},
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
                "max_seq_length_default_target": None,
            },
            vocab=vocab,
            train_vocab_opts={
                "other_opts": (
                    {
                        "spm": {"enable_sampling": True, "alpha": alpha},
                        "bpe": {"class": "SamplingBytePairEncoding", "breadth_prob": alpha},
                    }[sample]
                )
            },
            enabled=False,
        )

    # lrlin1e_5_393k vs lrlin1e_5_295k
    train_exp(  # 6.57 (vs 6.57 with lrlin1e_5_295k), slightly worse (not dev-other but others)
        f"v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_393k-speedpertV2-bpe10k",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "learning_rate_piecewise_steps": [393_000, 590_000, 652_000],  # total steps after 500 epochs: ~652k
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
        },
        vocab="bpe10k",
        enabled=False,
    )

    # Testing different vocabs together with sampling.
    for vocab, sample, alpha in [
        # spm20k no sampling: 6.12
        ("spm20k", "spm", 0.8),  # 6.20
        ("spm20k", "spm", 0.7),  # 6.32
        ("spm20k", "bpe", 0.01),  # 6.04
        # See archive/returnn-spm10-sample.config for playing around with alpha and checking avg seq len.
        # The lower the alpha, the longer the seq len, i.e. the more aggressive the sampling.
        # spm10k no sampling: 6.11
        ("spm10k", "spm", 0.9),  # 6.30
        ("spm10k", "spm", 0.8),  # 6.32
        ("spm10k", "spm", 0.7),  # 6.30
        ("spm10k", "spm", 0.5),  # 6.36
        ("spm10k", "spm", 0.3),  # 7.00
        ("spm10k", "bpe", 0.01),  # 6.00
        # alpha for SPM-BPE has a very different effect, and it causes the seq len to be much longer.
        # The higher the alpha, the longer (the reverse as for SPM Unigram).
        # See archive/returnn-spm_bpe10-sample.config.
        # spm_bpe10k no sampling: 6.34
        ("spm_bpe10k", "spm", 1e-5),  # 6.30
        ("spm_bpe10k", "spm", 1e-4),  # 6.26
        ("spm_bpe10k", "spm", 0.001),  # 6.32
        ("spm_bpe10k", "spm", 0.005),  # 6.31
        ("spm_bpe10k", "spm", 0.01),  # 6.33
        ("spm_bpe10k", "bpe", 0.01),  # 6.11
        # alpha for BPE is again a bit different, but more similar to SPM-BPE than SPM-Unigram.
        # See archive/returnn-bpe10-sample.config.
        # The higher the alpha, the longer the sequence, i.e. the more aggressive the sampling.
        # bpe10k no sampling: 6.57
        ("bpe10k", "bpe", 0.005),  # 6.44
        ("bpe10k", "bpe", 0.01),  # 6.33
        ("bpe10k", "bpe", 0.02),  # 6.56
        # spm4k no sampling: 6.20
        ("spm4k", "spm", 0.7),  # 6.59
        ("spm4k", "bpe", 0.01),  # 6.14
        # smp1k no sampling: 7.34
        ("spm1k", "bpe", 0.01),  # 8.11 (maybe worse because of max seq len?)
    ]:
        train_exp(
            f"v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-{vocab}"
            f"-{sample}Sample{str(alpha).replace('.', '').replace('-','_')}",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            },
            vocab=vocab,
            train_vocab_opts={
                "other_opts": (
                    {
                        "spm": {"enable_sampling": True, "alpha": alpha},
                        "bpe": {"class": "SamplingBytePairEncoding", "breadth_prob": alpha},
                    }[sample]
                )
            },
            enabled=False,
        )

    # Checking EOS.
    train_exp(  # 6.44 (vs without EOS 6.30), so EOS made it worse
        "v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-spm10k-eos-spmSample07",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "use_eos_postfix": True,
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"enable_sampling": True, "alpha": 0.7}},
        enabled=False,
    )

    # Test different feature normalization schemes.
    # Note: It seems the diff between dev-other and test-other is less here, probably du to the normalization.
    for name, model_opts in {
        None: None,  # {"dev-clean": 2.9, "dev-other": 6.3, "test-clean": 3.05, "test-other": 6.49}
        # featBN: {"dev-clean": 2.84, "dev-other": 6.29, "test-clean": 2.97, "test-other": 6.36}
        "featBN": {"feature_batch_norm": True},  # batch norm
        # featNorm: {"dev-clean": 2.88, "dev-other": 6.3, "test-clean": 2.97, "test-other": 6.55}
        "featNorm": {"feature_norm": True},  # normalize (on sequence level)
        # featGN: {"dev-clean": 2.82, "dev-other": 6.37, "test-clean": 2.99, "test-other": 6.43}
        "featGN": {"feature_stats": {"mean": feature_stats.mean, "std_dev": feature_stats.std_dev}},  # global norm
    }.items():
        train_exp(
            "v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-"
            f"{(name + '-') if name else ''}speedpertV2-spm10k-spmSample07",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            model_config=model_opts,
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            },
            vocab="spm10k",
            train_vocab_opts={"other_opts": {"enable_sampling": True, "alpha": 0.7}},
            enabled=False,
        )
    # featBN but without spmSample07 (baseline without featBN: 6.11)
    train_exp(  # 6.07, so again, featBN slightly better, also diff dev vs test is less
        "v6-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN-speedpertV2-spm10k",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
        },
        vocab="spm10k",
        enabled=False,
    )

    from i6_experiments.users.zeyer.nn_rf.batchnorm import BatchRenorm

    # Replacing batch norm in the Conformer Convolution Module with other normalization schemes.
    for name, opts in {
        # baseline: (batch-norm): {"dev-clean": 2.73, "dev-other": 6.33, "test-clean": 2.81, "test-other": 6.52}
        # batchRenorm: {"dev-clean": 2.69, "dev-other": 6.26, "test-clean": 2.91, "test-other": 6.55}
        "batchRenorm": rf.build_dict(
            BatchRenorm,
            use_mask=True,
            r_max=rf.build_dict(rf.PiecewiseLinearStepwiseScheduler, points={5_000: 1.0, 40_000: 3.0}),
            d_max=rf.build_dict(rf.PiecewiseLinearStepwiseScheduler, points={5_000: 0.0, 25_000: 5.0}),
        ),
        # groupNorm: {"dev-clean": 2.66, "dev-other": 6.38, "test-clean": 2.87, "test-other": 6.57}
        "groupNorm": rf.build_dict(rf.GroupNorm, num_groups=32),
        # layerNorm: {"dev-clean": 2.58, "dev-other": 6.39, "test-clean": 2.91, "test-other": 6.51}
        "layerNorm": rf.build_dict(rf.LayerNorm),
    }.items():
        for vocab, alpha in [("bpe10k", 0.01)]:  # [("bpe10k", 0.01), ("spm10k", 0.7)]:
            train_exp(
                f"v6-{name}-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-{vocab}"
                f"-{'spmSample' if vocab.startswith('spm') else 'bpeSample'}{str(alpha).replace('.', '')}",
                config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
                model_config={"conv_norm": opts},
                config_updates={
                    **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                    "optimizer.weight_decay": 1e-2,
                    "__train_audio_preprocess": speed_pert_librosa_config,
                    "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
                },
                vocab=vocab,
                train_vocab_opts={
                    "other_opts": (
                        {"enable_sampling": True, "alpha": alpha}
                        if vocab.startswith("spm")
                        else {"class": "SamplingBytePairEncoding", "breadth_prob": alpha}
                    )
                },
                enabled=False,
            )

    # relPosAttDef: Use the default RelPosSelfAttention instead of the Shawn et al 2018 style, old RETURNN way.
    enc_conformer_layer_default = rf.build_dict(
        rf.encoder.conformer.ConformerEncoderLayer,
        ff_activation=rf.build_dict(rf.relu_square),
        num_heads=8,
    )
    train_exp(  # 6.18 (no relPosAttDef: 6.30), so relPosAttDef is better
        "v6-relPosAttDef"
        "-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-spm10k-spmSample07",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"enable_sampling": True, "alpha": 0.7}},
        enabled=False,
    )
    train_exp(  # 5.94 (no relPosAttDef: 6.11), so relPosAttDef is better
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-spm10k",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
        },
        vocab="spm10k",
        enabled=False,
    )

    # Testing different vocabs together with sampling. Again. Now again with newer settings:
    # - relPosAttDef
    # - featBN
    # - maxSeqLenAudio19_5: Most importantly, this refers to audio len, thus it is independent of targets.
    for vocab, sample, alpha in [
        ("spm20k", None, None),  # 5.96
        ("spm20k", "spm", 0.7),  # 6.14
        ("spm20k", "bpe", 0.01),  # 6.13
        ("spm20k", "bpe", 0.02),
        ("bpe10k", None, None),  # 6.49
        ("bpe10k", "bpe", 0.01),  # 6.40
        ("spm10k", None, None),  # 6.00
        ("spm10k", "spm", 0.7),  # 6.20
        ("spm10k", "bpe", 0.01),  # 5.93 (!!)
        ("spm_bpe10k", None, None),  # 6.33
        ("spm_bpe10k", "spm", 1e-4),  # 6.26
        ("spm_bpe10k", "bpe", 0.01),  # 6.21
        ("spm4k", None, None),  # 6.07 (but test-other even better: 5.94?)
        ("spm4k", "spm", 0.7),  # 6.42
        ("spm4k", "bpe", 0.01),  # 6.05
        ("spm1k", None, None),  # 6.07
        ("spm1k", "spm", 0.7),  # 7.33
        ("spm1k", "bpe", 0.01),  # 6.13 (but dev-clean,test-* are better than no sampling)
        ("spm_bpe1k", None, None),  # 6.03
        ("spm_bpe1k", "bpe", 0.01),  # 6.05
        ("spm512", None, None),  # 6.08
        ("spm512", "bpe", 0.005),
        ("spm512", "bpe", 0.01),  # 6.08 (but test-* is better than spm512 without sampling)
        ("spm128", None, None),  # 6.37
        ("spm128", "bpe", 0.01),  # 6.40
    ]:
        train_exp(
            f"v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100"
            f"-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN-speedpertV2"
            f"-{vocab}" + (f"-{sample}Sample{str(alpha).replace('.', '').replace('-','_')}" if sample else ""),
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
                "max_seq_length_default_target": None,
                # Note on max seq len stats: Before, when we used max_seq_length_default_target=75 with bpe10k,
                # out of 281241 seqs in train, we removed only 71 seqs.
                # With max seq len 19.5 secs on the audio, we also remove exactly 71 seqs.
                "max_seq_length_default_input": 19.5 * _raw_sample_rate,
            },
            vocab=vocab,
            train_vocab_opts=(
                {
                    "other_opts": (
                        {
                            "spm": {"enable_sampling": True, "alpha": alpha},
                            "bpe": {"class": "SamplingBytePairEncoding", "breadth_prob": alpha},
                        }[sample]
                    )
                }
                if sample
                else None
            ),
        )
    # Debugging `CUDA error: an illegal memory access` https://github.com/rwth-i6/returnn/issues/1577 ...
    for name in [
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm128",
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm128-bpeSample001",
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm1k-spmSample07",
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm512-bpeSample001",
        "v6-relPosAttDef-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-maxSeqLenAudio19_5-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm512",
    ]:
        _train_experiments[name].get_training_job().set_env("CUDA_LAUNCH_BLOCKING", "1")

    train_exp(  # 5.78
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-speedpertV2-spm10k",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
        },
        vocab="spm10k",
        enabled=False,
    )

    # Now with featBN and bpeSample001.
    train_exp(  # 5.77
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # Now aux Trafo decoder with only 2 layers (aedLossN2).
    train_exp(  # 5.81 (but dev-clean, test-clean, test-other are better)
        "v6-relPosAttDef-aedLossN2-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=2),  # purely used for training
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
        enabled=False,
    )

    # CTC label smoothing (ctcLS01).
    train_exp(
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001-ctcLS01",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            "ctc_label_smoothing": 0.1,
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # CTC label smoothing excluding blank (ctcLS01xB).
    train_exp(  # 5.78 (but dev-clean, test-clean, test-other are better than without ctcLS01xB!)
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001-ctcLS01xB",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            "ctc_label_smoothing": 0.1,
            "ctc_label_smoothing_exclude_blank": True,
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # Blank separated (blankSep).
    for vocab, alpha in [
        ("bpe10k", 0.01),
        ("spm10k", 0.01),  # 5.73 (!!!)
        ("spm512", 0.01),
    ]:
        train_exp(
            "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
            f"-speedpertV2-{vocab}-bpeSample{str(alpha).replace('.', '')}-blankSep",
            config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
            model_config={
                "enc_conformer_layer": enc_conformer_layer_default,
                "feature_batch_norm": True,
                "out_blank_separated": True,
            },
            config_updates={
                **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
                "optimizer.weight_decay": 1e-2,
                "__train_audio_preprocess": speed_pert_librosa_config,
                "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
                "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            },
            vocab="spm10k",
            train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": alpha}},
        )

    # Blank separated (blankSep) with CTC label smoothing excluding blank (ctcLS01xB).
    train_exp(  # 6.14
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001-blankSep-ctcLS01xB",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={
            "enc_conformer_layer": enc_conformer_layer_default,
            "feature_batch_norm": True,
            "out_blank_separated": True,
        },
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            "ctc_label_smoothing": 0.1,
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # Now variational noise / weight noise (vn0025).
    train_exp(  # 5.91 (so worse on dev-other, but it's better on test-other)
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-vn0025"
        "-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "variational_noise": 0.0025,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # Now weight dropout (wdrop01).
    train_exp(  # 5.96
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-wdrop01"
        "-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={"enc_conformer_layer": enc_conformer_layer_default, "feature_batch_norm": True},
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "weight_dropout": 0.01,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
    )

    # Log prob normed gradient
    train_exp(  # 6.14
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001-lpNormedGrad",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={
            "enc_conformer_layer": enc_conformer_layer_default,
            "feature_batch_norm": True,
        },
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            "log_prob_normed_grad": {
                "func": {"clamp_min": 0.5, "clamp_max": 1.1, "scale_type": "inv_num_labels", "prior_exp": 1.0}
            },
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
        epilog=[
            serialization.NonhashedCode(f"sys.path.append({gs.BASE_DIR + '/projects/2024-alignment-analysis'!r})\n")
        ],
    )

    # Log prob normed gradient (lpNormedGrad) with blank separated (blankSep)
    train_exp(  # 6.14
        "v6-relPosAttDef-aedLoss-bhv20-11gb-f32-bs15k-accgrad1-mgpu4-pavg100-wd1e_2-lrlin1e_5_295k-featBN"
        "-speedpertV2-spm10k-bpeSample001-blankSep-lpNormedGrad",
        config_11gb_v6_f32_accgrad1_mgpu4_pavg100_wd1e_4,
        model_config={
            "enc_conformer_layer": enc_conformer_layer_default,
            "feature_batch_norm": True,
            "out_blank_separated": True,
        },
        config_updates={
            **_get_cfg_lrlin_oclr_by_bs_nep(15_000, 500),
            "optimizer.weight_decay": 1e-2,
            "__train_audio_preprocess": speed_pert_librosa_config,
            "speed_pert_discrete_values": [0.7, 0.8, 0.9, 1.0, 1.1],
            "aux_attention_decoder": rf.build_dict(TransformerDecoder, num_layers=6),  # purely used for training
            "log_prob_normed_grad": {
                "func": {"clamp_min": 0.5, "clamp_max": 1.1, "scale_type": "inv_num_labels", "prior_exp": 1.0}
            },
        },
        vocab="spm10k",
        train_vocab_opts={"other_opts": {"class": "SamplingBytePairEncoding", "breadth_prob": 0.01}},
        epilog=[
            serialization.NonhashedCode(f"sys.path.append({gs.BASE_DIR + '/projects/2024-alignment-analysis'!r})\n")
        ],
    )


_train_experiments: Dict[str, ModelWithCheckpoints] = {}


# noinspection PyShadowingNames
def train_exp(
    name: str,
    config: Dict[str, Any],
    *,
    model_def: Optional[Union[ModelDefWithCfg, ModelDef[Model]]] = None,
    vocab: str = "bpe10k",
    train_vocab_opts: Optional[Dict[str, Any]] = None,
    train_def: Optional[TrainDef[Model]] = None,
    model_config: Optional[Dict[str, Any]] = None,
    config_updates: Optional[Dict[str, Any]] = None,
    config_deletes: Optional[Sequence[str]] = None,
    post_config_updates: Optional[Dict[str, Any]] = None,
    epilog: Sequence[serialization.SerializerObject] = (),
    num_epochs: int = 2000,
    gpu_mem: Optional[int] = 24,
    num_processes: Optional[int] = None,
    time_rqmt: Optional[int] = None,  # set this to 1 or below to get the fast test queue
    enabled: bool = True,
) -> Optional[ModelWithCheckpoints]:
    """
    Train experiment
    """
    from i6_experiments.users.zeyer.train_v3 import train
    from i6_experiments.users.zeyer.recog import recog_training_exp
    from i6_experiments.users.zeyer.datasets.librispeech import get_librispeech_task_raw_v2

    if not enabled:
        return None

    if _sis_prefix is None:
        _sis_setup_global_prefix()

    prefix = _sis_prefix + "/" + name
    task = get_librispeech_task_raw_v2(vocab=vocab, train_vocab_opts=train_vocab_opts)
    config = config.copy()
    config = dict_update_deep(config, config_updates, config_deletes)
    if "__num_epochs" in config:
        num_epochs = config.pop("__num_epochs")
    if "__gpu_mem" in config:
        gpu_mem = config.pop("__gpu_mem")
    if "__num_processes" in config:
        num_processes = config.pop("__num_processes")
    if "__train_audio_preprocess" in config:
        task: Task = copy.copy(task)
        task.train_dataset = copy.copy(task.train_dataset)
        task.train_dataset.train_audio_preprocess = config.pop("__train_audio_preprocess")

    if not model_def:
        model_def = ctc_model_def
    if model_config:
        model_def = ModelDefWithCfg(model_def, model_config)
    if not train_def:
        train_def = ctc_training
    model_with_checkpoint = train(
        prefix,
        task=task,
        config=config,
        post_config=dict_update_deep(post_config, post_config_updates),
        epilog=epilog,
        model_def=model_def,
        train_def=train_def,
        num_epochs=num_epochs,
        gpu_mem=gpu_mem,
        num_processes=num_processes,
        distributed_launch_cmd="torchrun" if num_processes else "mpirun",
        time_rqmt=time_rqmt,
    )

    recog_post_proc_funcs = []
    if config.get("use_eos_postfix", False):
        recog_post_proc_funcs.append(_remove_eos_label_v2)
    recog_training_exp(
        prefix, task, model_with_checkpoint, recog_def=model_recog, recog_post_proc_funcs=recog_post_proc_funcs
    )

    _train_experiments[name] = model_with_checkpoint
    return model_with_checkpoint


def _remove_eos_label_v2(res: RecogOutput) -> RecogOutput:
    from i6_experiments.users.zeyer.datasets.score_results import RecogOutput
    from i6_core.returnn.search import SearchRemoveLabelJob

    return RecogOutput(SearchRemoveLabelJob(res.output, remove_label="</s>", output_gzip=True).out_search_results)


_sis_prefix: Optional[str] = None


def _sis_setup_global_prefix(prefix_name: Optional[str] = None):
    if not prefix_name:
        from i6_experiments.users.zeyer.utils.sis_setup import get_setup_prefix_for_module

        prefix_name = get_setup_prefix_for_module(__name__)
    global _sis_prefix
    _sis_prefix = prefix_name


def ctc_model_def(*, epoch: int, in_dim: Dim, target_dim: Dim) -> Model:
    """Function is run within RETURNN."""
    from returnn.config import get_global_config

    in_dim, epoch  # noqa
    config = get_global_config()  # noqa
    enc_aux_logits = config.typed_value("aux_loss_layers")
    num_enc_layers = config.int("num_enc_layers", 12)
    # real input is raw audio, internally it does logmel
    in_dim = Dim(name="logmel", dimension=_log_mel_feature_dim, kind=Dim.Types.Feature)

    conv_norm = config.typed_value("conv_norm", None)
    enc_conformer_layer = config.typed_value("enc_conformer_layer", None)
    if enc_conformer_layer:
        assert not conv_norm, "set only enc_conformer_layer or conv_norm, not both"
        assert isinstance(enc_conformer_layer, dict) and "class" in enc_conformer_layer
    else:
        enc_conformer_layer = rf.build_dict(
            rf.encoder.conformer.ConformerEncoderLayer,
            conv_norm=conv_norm or {"class": "rf.BatchNorm", "use_mask": True},
            self_att=rf.build_dict(
                rf.RelPosSelfAttention,
                # Shawn et al 2018 style, old RETURNN way.
                with_bias=False,
                with_linear_pos=False,
                with_pos_bias=False,
                learnable_pos_emb=True,
                separate_pos_emb_per_head=False,
            ),
            ff_activation=rf.build_dict(rf.relu_square),
            num_heads=8,
        )

    return Model(
        in_dim,
        num_enc_layers=num_enc_layers,
        enc_model_dim=Dim(name="enc", dimension=512, kind=Dim.Types.Feature),
        enc_ff_dim=Dim(name="enc-ff", dimension=2048, kind=Dim.Types.Feature),
        enc_conformer_layer=enc_conformer_layer,
        target_dim=target_dim,
        blank_idx=target_dim.dimension,
        bos_idx=_get_bos_idx(target_dim),
        eos_idx=_get_eos_idx(target_dim),
        enc_aux_logits=enc_aux_logits or (),
    )


ctc_model_def: ModelDef[Model]
ctc_model_def.behavior_version = 21
ctc_model_def.backend = "torch"
ctc_model_def.batch_size_factor = _batch_size_factor


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


def ctc_training(*, model: Model, data: rf.Tensor, data_spatial_dim: Dim, targets: rf.Tensor, targets_spatial_dim: Dim):
    """Function is run within RETURNN."""
    from returnn.config import get_global_config

    config = get_global_config()  # noqa
    aux_loss_layers = config.typed_value("aux_loss_layers")
    aux_loss_scales = config.typed_value("aux_loss_scales", ([1.0] * len(aux_loss_layers)) if aux_loss_layers else None)
    aed_loss_scale = config.float("aed_loss_scale", 1.0)
    use_normalized_loss = config.bool("use_normalized_loss", True)

    if data.feature_dim and data.feature_dim.dimension == 1:
        data = rf.squeeze(data, axis=data.feature_dim)
    assert not data.feature_dim  # raw audio

    if config.bool("use_eos_postfix", False):
        targets, (targets_spatial_dim,) = rf.pad(
            targets, axes=[targets_spatial_dim], padding=[(0, 1)], value=model.eos_idx
        )

    collected_outputs = {}
    logits, enc, enc_spatial_dim = model(data, in_spatial_dim=data_spatial_dim, collected_outputs=collected_outputs)
    if aux_loss_layers:
        for i, layer_idx in enumerate(aux_loss_layers):
            if layer_idx > len(model.encoder.layers):
                continue
            linear = getattr(model, f"enc_aux_logits_{layer_idx}")
            aux_logits = linear(collected_outputs[str(layer_idx - 1)])
            aux_log_probs = model.log_probs_wb_from_logits(aux_logits)
            aux_loss = rf.ctc_loss(
                logits=aux_log_probs,
                logits_normalized=True,
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
            # decoded, decoded_spatial_dim = rf.ctc_greedy_decode(aux_logits, in_spatial_dim=enc_spatial_dim)
            # error = rf.edit_distance(
            #     a=decoded, a_spatial_dim=decoded_spatial_dim, b=targets, b_spatial_dim=targets_spatial_dim
            # )
            # error.mark_as_loss("label", as_error=True, custom_inv_norm_factor=targets_spatial_dim.get_size_tensor())

    log_probs = model.log_probs_wb_from_logits(logits)
    loss = rf.ctc_loss(
        logits=log_probs,
        logits_normalized=True,
        targets=targets,
        input_spatial_dim=enc_spatial_dim,
        targets_spatial_dim=targets_spatial_dim,
        blank_index=model.blank_idx,
    )
    loss.mark_as_loss(
        "ctc",
        custom_inv_norm_factor=targets_spatial_dim.get_size_tensor(),
        use_normalized_loss=use_normalized_loss,
    )

    if model.decoder:
        # potentially also other types but just assume
        # noinspection PyTypeChecker
        decoder: TransformerDecoder = model.decoder

        input_labels, (targets_w_eos_spatial_dim,) = rf.pad(
            targets, axes=[targets_spatial_dim], padding=[(1, 0)], value=model.bos_idx
        )
        targets_w_eos, _ = rf.pad(
            targets,
            axes=[targets_spatial_dim],
            padding=[(0, 1)],
            value=model.eos_idx,
            out_dims=[targets_w_eos_spatial_dim],
        )

        batch_dims = data.remaining_dims(data_spatial_dim)
        logits, _ = model.decoder(
            input_labels,
            spatial_dim=targets_w_eos_spatial_dim,
            encoder=decoder.transform_encoder(enc, axis=enc_spatial_dim),
            state=model.decoder.default_initial_state(batch_dims=batch_dims),
        )

        logits_packed, pack_dim = rf.pack_padded(
            logits, dims=batch_dims + [targets_w_eos_spatial_dim], enforce_sorted=False
        )
        targets_packed, _ = rf.pack_padded(
            targets_w_eos, dims=batch_dims + [targets_w_eos_spatial_dim], enforce_sorted=False, out_dim=pack_dim
        )

        log_prob = rf.log_softmax(logits_packed, axis=model.target_dim)
        log_prob = rf.label_smoothed_log_prob_gradient(log_prob, 0.1, axis=model.target_dim)
        loss = rf.cross_entropy(
            target=targets_packed, estimated=log_prob, estimated_type="log-probs", axis=model.target_dim
        )
        loss.mark_as_loss("aed_ce", scale=aed_loss_scale, use_normalized_loss=use_normalized_loss)

        best = rf.reduce_argmax(logits_packed, axis=model.target_dim)
        frame_error = best != targets_packed
        frame_error.mark_as_loss(name="aed_fer", as_error=True)


ctc_training: TrainDef[Model]
ctc_training.learning_rate_control_error_measure = "ctc"


def model_recog(
    *,
    model: Model,
    data: Tensor,
    data_spatial_dim: Dim,
) -> Tuple[Tensor, Tensor, Dim, Dim]:
    """
    Function is run within RETURNN.

    Earlier we used the generic beam_search function,
    but now we just directly perform the search here,
    as this is overall simpler and shorter.

    :return:
        recog results including beam {batch, beam, out_spatial},
        log probs {batch, beam},
        out_spatial_dim,
        final beam_dim
    """
    batch_dims = data.remaining_dims((data_spatial_dim, data.feature_dim))
    logits, enc, enc_spatial_dim = model(data, in_spatial_dim=data_spatial_dim)
    beam_size = 12

    # Eager-mode implementation of beam search.
    # Initial state.
    beam_dim = Dim(1, name="initial-beam")
    batch_dims_ = [beam_dim] + batch_dims
    seq_log_prob = rf.constant(0.0, dims=batch_dims_)  # Batch, Beam

    label_log_prob = model.log_probs_wb_from_logits(logits)  # Batch, Spatial, Vocab
    label_log_prob = rf.where(
        enc_spatial_dim.get_mask(),
        label_log_prob,
        rf.sparse_to_dense(model.blank_idx, axis=model.wb_target_dim, label_value=0.0, other_value=-1.0e30),
    )
    label_log_prob_pre_filter, (backrefs_pre_filter,), pre_filter_beam_dim = rf.top_k(
        label_log_prob, k_dim=Dim(beam_size, name=f"pre-filter-beam"), axis=[model.wb_target_dim]
    )  # seq_log_prob, backrefs_global: Batch, Spatial, PreFilterBeam. backrefs_pre_filter -> Vocab
    label_log_prob_pre_filter_ta = TensorArray.unstack(
        label_log_prob_pre_filter, axis=enc_spatial_dim
    )  # t -> Batch, PreFilterBeam
    backrefs_pre_filter_ta = TensorArray.unstack(backrefs_pre_filter, axis=enc_spatial_dim)  # t -> Batch, PreFilterBeam

    max_seq_len = int(enc_spatial_dim.get_dim_value())
    seq_targets = []
    seq_backrefs = []
    for t in range(max_seq_len):
        # Filter out finished beams
        seq_log_prob = seq_log_prob + label_log_prob_pre_filter_ta[t]  # Batch, InBeam, PreFilterBeam
        seq_log_prob, (backrefs, target), beam_dim = rf.top_k(
            seq_log_prob, k_dim=Dim(beam_size, name=f"dec-step{t}-beam"), axis=[beam_dim, pre_filter_beam_dim]
        )  # seq_log_prob, backrefs, target: Batch, Beam. backrefs -> InBeam. target -> PreFilterBeam.
        target = rf.gather(backrefs_pre_filter_ta[t], indices=target)  # Batch, Beam -> Vocab
        seq_targets.append(target)
        seq_backrefs.append(backrefs)

    # Backtrack via backrefs, resolve beams.
    seq_targets_ = []
    indices = rf.range_over_dim(beam_dim)  # FinalBeam -> FinalBeam
    for backrefs, target in zip(seq_backrefs[::-1], seq_targets[::-1]):
        # indices: FinalBeam -> Beam
        # backrefs: Beam -> PrevBeam
        seq_targets_.insert(0, rf.gather(target, indices=indices))
        indices = rf.gather(backrefs, indices=indices)  # FinalBeam -> PrevBeam

    seq_targets__ = TensorArray(seq_targets_[0])
    for target in seq_targets_:
        seq_targets__ = seq_targets__.push_back(target)
    out_spatial_dim = enc_spatial_dim
    seq_targets = seq_targets__.stack(axis=out_spatial_dim)

    return seq_targets, seq_log_prob, out_spatial_dim, beam_dim


# RecogDef API
model_recog: RecogDef[Model]
model_recog.output_with_beam = True
model_recog.output_blank_label = "<blank>"
model_recog.batch_size_dependent = False  # not totally correct, but we treat it as such...


class Model(rf.Module):
    """Model definition"""

    def __init__(
        self,
        in_dim: Dim,
        *,
        num_enc_layers: int = 12,
        target_dim: Dim,
        wb_target_dim: Optional[Dim] = None,
        blank_idx: int,
        eos_idx: int,
        bos_idx: int,
        enc_aux_logits: Sequence[int] = (),  # layers
        enc_model_dim: Dim = Dim(name="enc", dimension=512),
        enc_ff_dim: Dim = Dim(name="enc-ff", dimension=2048),
        enc_conformer_layer: Optional[Dict[str, Any]] = None,
    ):
        super(Model, self).__init__()

        import numpy
        from returnn.config import get_global_config

        config = get_global_config(return_empty_if_none=True)

        enc_layer_drop = config.float("enc_layer_drop", 0.0)
        if enc_layer_drop:
            enc_sequential = functools.partial(SequentialLayerDrop, layer_drop=enc_layer_drop)
        else:
            enc_sequential = rf.Sequential

        self.in_dim = in_dim
        self.encoder = ConformerEncoder(
            in_dim,
            enc_model_dim,
            ff_dim=enc_ff_dim,
            input_layer=ConformerConvSubsample(
                in_dim,
                out_dims=[Dim(32, name="conv1"), Dim(64, name="conv2"), Dim(64, name="conv3")],
                filter_sizes=[(3, 3), (3, 3), (3, 3)],
                pool_sizes=[(1, 2)],
                strides=[(1, 1), (3, 1), (2, 1)],
            ),
            encoder_layer=enc_conformer_layer,
            num_layers=num_enc_layers,
            sequential=enc_sequential,
        )

        self.target_dim = target_dim
        self.blank_idx = blank_idx
        self.eos_idx = eos_idx
        self.bos_idx = bos_idx  # for non-blank labels; for with-blank labels, we use bos_idx=blank_idx

        if not wb_target_dim:
            wb_target_dim = target_dim + 1
        for i in enc_aux_logits:
            setattr(self, f"enc_aux_logits_{i}", rf.Linear(self.encoder.out_dim, wb_target_dim))
        self.enc_logits = rf.Linear(self.encoder.out_dim, wb_target_dim)
        self.wb_target_dim = wb_target_dim
        self.out_blank_separated = config.bool("out_blank_separated", False)

        if target_dim.vocab and not wb_target_dim.vocab:
            from returnn.datasets.util.vocabulary import Vocabulary

            # Just assumption for code now, might extend this later.
            assert wb_target_dim.dimension == target_dim.dimension + 1 and blank_idx == target_dim.dimension
            vocab_labels = list(target_dim.vocab.labels) + [model_recog.output_blank_label]
            wb_target_dim.vocab = Vocabulary.create_vocab_from_labels(
                vocab_labels, user_defined_symbols={model_recog.output_blank_label: blank_idx}
            )

        ctc_label_smoothing = config.float("ctc_label_smoothing", 0.0)
        ctc_label_smoothing_exclude_blank = config.bool("ctc_label_smoothing_exclude_blank", self.out_blank_separated)
        if not self.out_blank_separated:
            self.ctc_label_smoothing_opts = {
                "smoothing": ctc_label_smoothing,
                "axis": self.wb_target_dim,
                "exclude_labels": [self.blank_idx] if ctc_label_smoothing_exclude_blank else None,
            }
        else:  # separate blank
            assert ctc_label_smoothing_exclude_blank  # required with separate blank
            self.ctc_label_smoothing_opts = {
                "smoothing": ctc_label_smoothing,
                "axis": self.target_dim,
            }
        self.log_prob_normed_grad_opts = config.typed_value("log_prob_normed_grad", None)

        self.feature_batch_norm = None
        if config.bool("feature_batch_norm", False):
            self.feature_batch_norm = rf.BatchNorm(self.in_dim, affine=False, use_mask=True)
        self.feature_norm = config.bool("feature_norm", False)
        self.feature_stats = None
        feature_stats = config.typed_value("feature_stats")
        if feature_stats:
            assert isinstance(feature_stats, dict)
            self.feature_stats = rf.ParameterList(
                {
                    k: rf.Parameter(
                        rf.convert_to_tensor(numpy.loadtxt(v), dims=[self.in_dim], dtype=rf.get_default_float_dtype()),
                        auxiliary=True,
                    )
                    for k, v in feature_stats.items()
                }
            )

        self._specaugment_opts = {
            "steps": config.typed_value("specaugment_steps") or (0, 1000, 2000),
            "max_consecutive_spatial_dims": config.typed_value("specaugment_max_consecutive_spatial_dims") or 20,
            "max_consecutive_feature_dims": config.typed_value("specaugment_max_consecutive_feature_dims")
            or (_log_mel_feature_dim // 5),
            "num_spatial_mask_factor": config.typed_value("specaugment_num_spatial_mask_factor") or 100,
        }

        self._mixup = None
        if config.typed_value("mixup", None) is not None:
            from i6_experiments.users.zeyer.returnn.models.rf_mixup import Mixup, MixupOpts

            self._mixup = Mixup(feature_dim=self.in_dim, opts=MixupOpts(**config.typed_value("mixup")))

        self.decoder = None
        aux_attention_decoder = config.typed_value("aux_attention_decoder", None)
        if aux_attention_decoder:
            assert isinstance(aux_attention_decoder, dict)
            aux_attention_decoder = aux_attention_decoder.copy()
            aux_attention_decoder.setdefault("class", "returnn.frontend.decoder.transformer.TransformerDecoder")
            if isinstance(aux_attention_decoder.get("model_dim", None), int):
                aux_attention_decoder["model_dim"] = Dim(aux_attention_decoder["model_dim"], name="dec_model")
            self.decoder = rf.build_from_dict(aux_attention_decoder, encoder_dim=enc_model_dim, vocab_dim=target_dim)

        vn = config.typed_value("variational_noise", None)
        if vn:
            # Use some blacklist. I think the same blacklist as for weight decay is reasonable.
            # Usually sth like: ["rf.Embedding", "rf.LearnedRelativePositionalEncoding"]
            blacklist = config.typed_value("optimizer")["weight_decay_modules_blacklist"]
            blacklist = tuple(eval(name, {"rf": rf}) for name in blacklist)
            for mod in self.modules():
                if isinstance(mod, blacklist):
                    continue
                for param_name, param in mod.named_parameters(recurse=False):
                    if param_name.endswith("bias"):  # no bias
                        continue
                    if param.auxiliary:
                        continue
                    rf.weight_noise(mod, param_name, std=vn)

        weight_dropout = config.typed_value("weight_dropout", None)
        if weight_dropout:
            # Use some blacklist. I think the same blacklist as for weight decay is reasonable.
            # Usually sth like: ["rf.Embedding", "rf.LearnedRelativePositionalEncoding"]
            blacklist = config.typed_value("optimizer")["weight_decay_modules_blacklist"]
            blacklist = tuple(eval(name, {"rf": rf}) for name in blacklist)
            for mod in self.modules():
                if isinstance(mod, blacklist):
                    continue
                for param_name, param in mod.named_parameters(recurse=False):
                    if param_name.endswith("bias"):  # no bias
                        continue
                    if param.auxiliary:
                        continue
                    rf.weight_dropout(mod, param_name, drop_prob=weight_dropout)

    def __call__(
        self,
        source: Tensor,
        *,
        in_spatial_dim: Dim,
        collected_outputs: Optional[Dict[str, Tensor]] = None,
    ) -> Tuple[Tensor, Tensor, Dim]:
        """encode, get logits"""
        # log mel filterbank features
        source, in_spatial_dim = rf.audio.log_mel_filterbank_from_raw(
            source,
            in_spatial_dim=in_spatial_dim,
            out_dim=self.in_dim,
            sampling_rate=16_000,
        )
        if self.feature_batch_norm:
            source = self.feature_batch_norm(source)
        if self.feature_norm:
            source = rf.normalize(source, axis=in_spatial_dim)
        if self.feature_stats:
            source = (source - self.feature_stats.mean) / self.feature_stats.std_dev
        if self._mixup:
            source = self._mixup(source, spatial_dim=in_spatial_dim)
        # SpecAugment
        source = rf.audio.specaugment(
            source,
            spatial_dim=in_spatial_dim,
            feature_dim=self.in_dim,
            **self._specaugment_opts,
        )
        # Encoder including convolutional frontend
        enc, enc_spatial_dim = self.encoder(source, in_spatial_dim=in_spatial_dim, collected_outputs=collected_outputs)
        logits = self.enc_logits(enc)
        return logits, enc, enc_spatial_dim

    def log_probs_wb_from_logits(self, logits: Tensor) -> Tensor:
        """
        :return: log probs with blank from logits (wb_target_dim)
            If out_blank_separated, we use a separate sigmoid for the blank.
        """
        if not self.out_blank_separated:
            log_probs = rf.log_softmax(logits, axis=self.wb_target_dim)
            log_probs = self._maybe_apply_on_log_probs(log_probs)
            return log_probs
        else:  # separate blank
            assert self.blank_idx == self.target_dim.dimension  # not implemented otherwise
            dummy_blank_feat_dim = Dim(1, name="blank_feat")
            logits_wo_blank, logits_blank = rf.split(
                logits, axis=self.wb_target_dim, out_dims=[self.target_dim, dummy_blank_feat_dim]
            )
            log_probs_wo_blank = rf.log_softmax(logits_wo_blank, axis=self.target_dim)
            log_probs_wo_blank = self._maybe_apply_on_log_probs(log_probs_wo_blank)
            log_probs_blank = rf.log_sigmoid(logits_blank)
            log_probs_emit = rf.squeeze(rf.log_sigmoid(-logits_blank), axis=dummy_blank_feat_dim)
            log_probs, _ = rf.concat(
                (log_probs_wo_blank + log_probs_emit, self.target_dim),
                (log_probs_blank, dummy_blank_feat_dim),
                out_dim=self.wb_target_dim,
            )
            log_probs.feature_dim = self.wb_target_dim
            return log_probs

    def _maybe_apply_on_log_probs(self, log_probs: Tensor) -> Tensor:
        log_probs = self._maybe_apply_log_probs_normed_grad(log_probs)
        log_probs = rf.label_smoothed_log_prob_gradient(log_probs, **self.ctc_label_smoothing_opts)
        return log_probs

    def _maybe_apply_log_probs_normed_grad(self, log_probs: Tensor) -> Tensor:
        if not self.log_prob_normed_grad_opts:
            return log_probs

        from alignments.util import normed_gradient, NormedGradientFuncInvPrior

        opts: Dict[str, Any] = self.log_prob_normed_grad_opts.copy()
        func_opts = opts.pop("func")
        assert isinstance(func_opts, dict)
        func_opts = func_opts.copy()
        assert func_opts.get("class", "inv_prior") == "inv_prior"  # only case for now
        func_opts.pop("class", None)
        func = NormedGradientFuncInvPrior(**func_opts)

        log_probs_ = log_probs.copy_template()
        log_probs_.raw_tensor = normed_gradient(
            log_probs.raw_tensor, feat_axis=log_probs.feature_dim_axis, **opts, func=func
        )
        return log_probs_
