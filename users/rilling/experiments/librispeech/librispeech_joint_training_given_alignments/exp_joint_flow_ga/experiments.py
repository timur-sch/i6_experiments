import copy
import os
import numpy as np
from sisyphus import tk
from dataclasses import asdict

from i6_experiments.users.rilling.experiments.librispeech.librispeech_x_vectors.storage import x_vector_extractions

from ..data import (
    build_training_dataset,
    build_test_dataset,
    build_tts_forward_dataset,
    TrainingDatasetSettings,
    get_binary_lm,
    get_arpa_lm,
    get_text_lexicon,
    get_bliss_corpus_dict
)
from ..config import get_training_config, get_extract_durations_forward__config, get_forward_config, get_search_config
from ..pipeline import training, forward, search, compute_phoneme_pred_accuracy
from i6_experiments.users.rilling.experiments.librispeech.common.tts_eval import tts_eval

from ..default_tools import RETURNN_COMMON, RETURNN_PYTORCH_EXE, RETURNN_PYTORCH_ASR_SEARCH_EXE, MINI_RETURNN_ROOT
from ..pytorch_networks.shared.configs import (
    SpecaugConfig,
    ModelConfigV1,
    ModelConfigV2,
    VGG4LayerActFrontendV1Config_mod,
    TextEncoderConfig,
    EmbeddingTextEncoderConfig,
    FlowDecoderConfig,
    PhonemePredictionConfig,
    PhonemePredictionConfigCNN
)

from ..storage import tts_models


def get_glow_joint_flow_ga(x_vector_exp, joint_exps, tts_exps, gl_checkpoint):
    """
    Experiments training Glow-TTS with an additional auxiliary loss using a simple model for phoneme reconstruction (FFN or CNN).
    Other than the models in ../exp_joint these models also use the given external alignment for the Glow-TTS training so MAS/Viterbi is completely omitted
    """

    prefix = "experiments/librispeech/joint_training/given_alignments/raw_audio/joint_models/flow_given_alignment/"
    experiments = {}

    def run_exp(
        name,
        args,
        dataset,
        test_dataset,
        num_epochs=100,
        use_custom_engine=False,
        training_args={},
        forward_args={},
        search_args={},
        keep_epochs=None,
        phoneme_pred=True,
        encoder_phoneme_pred=False,
        eval_invertibility=False,
        tts_eval_datasets=None,
    ):
        """Creates the jobs for training, TTS generation/forwarding and phoneme prediction evaluation

        :param str name: Name of the experiment used for alias
        :param dict args: General arguments used for Returnn config generation
        :param TrainingDataset dataset: Dataset used for training
        :param dict test_dataset: Dictionary containing datasets used for phoneme prediction evaluation
        :param int num_epochs: Number of epochs for training, defaults to 100
        :param bool use_custom_engine: whether a custom engine should be used in Returnn, defaults to False
        :param dict training_args: Additional arguments passed to the training config and the train steps, defaults to {}
        :param dict forward_args: Additional arguments passed to the TTS forward config and forward steps, defaults to {}
        :param dict search_args: Additional arguments passed to the phoneme prediction and respective steps, defaults to {}
        :param list[int] keep_epochs: List containing the number of checkpoints that are not supposed to be deleted during training, defaults to None
        :param bool phoneme_pred: whether phoneme prediction using the inverse decoder output should be run and evaluated, uses test_dataset for evaluation, defaults to True
        :param bool encoder_phoneme_pred: whether phoneme prediction using the encoder output should be run, uses test_dataset for evaluation, defaults to False
        :param bool eval_invertibility: whether invertibility of the models coupling blocks should be run, defaults to False
        :param dict tts_eval_datasets: Dictionary of datasets to be used for TTS evaluation (autoMOS, NISQA), defaults to None
        :return dict: Dictionary containing all the jobs created for
        """
        exp = {}

        training_config = get_training_config(
            training_datasets=dataset,
            **args,
            training_args=training_args,
            use_custom_engine=use_custom_engine,
            keep_epochs=keep_epochs,
        ) 

        if phoneme_pred:
            phoneme_pred_config = get_search_config(
                **args,
                search_args=search_args,
                target="phoneme"
            )

        if eval_invertibility:
            forward_config_invert = get_forward_config(
                forward_dataset=dataset, **{**args, **{"config": {"batch_size": 50 * 16000}}}, target="invertibility"
            )

        if encoder_phoneme_pred:
            encoder_phoneme_pred_config = get_search_config(**args, search_args=search_args, target="encoder_phoneme")

        train_job = training(
            config=training_config,
            returnn_exe=RETURNN_PYTORCH_EXE,
            returnn_root=MINI_RETURNN_ROOT,
            prefix=prefix + name,
            num_epochs=num_epochs,
        )

        exp["train_job"] = train_job

        for ds_k, ds in tts_eval_datasets.items():
            forward_config_gl = get_forward_config(
                forward_dataset=ds,
                **{**args, **{"config": {"batch_size": 50 * 16000}}},
                forward_args={
                    **forward_args,
                    "gl_net_checkpoint": gl_checkpoint["checkpoint"],
                    "gl_net_config": gl_checkpoint["config"],
                },
                target="corpus_gl",
            )
            forward_job_gl = tts_eval(
                checkpoint=train_job.out_checkpoints[num_epochs],
                prefix_name=prefix + name,
                returnn_config=forward_config_gl,
                returnn_exe=RETURNN_PYTORCH_EXE,
                returnn_exe_asr=RETURNN_PYTORCH_ASR_SEARCH_EXE,
                returnn_root=MINI_RETURNN_ROOT,
                vocoder="gl",
                nisqa_eval=True, 
                swer_eval=True,
                swer_eval_corpus_key=ds_k
            )

        if phoneme_pred:
            compute_phoneme_pred_accuracy(
                prefix + name,
                phoneme_pred_config,
                recognition_datasets=test_dataset,
                checkpoint=train_job.out_checkpoints[num_epochs],
                returnn_exe=RETURNN_PYTORCH_EXE,
                returnn_root=MINI_RETURNN_ROOT
            )

        if encoder_phoneme_pred:
            compute_phoneme_pred_accuracy(
                prefix + name,
                encoder_phoneme_pred_config,
                recognition_datasets=test_dataset,
                checkpoint=train_job.out_checkpoints[num_epochs],
                returnn_exe=RETURNN_PYTORCH_EXE,
                returnn_root=MINI_RETURNN_ROOT,
                target="encoder_phoneme"
            )

        if eval_invertibility:
            forward_job = forward(
                checkpoint=train_job.out_checkpoints[num_epochs],
                config=forward_config_invert,
                returnn_exe=RETURNN_PYTORCH_EXE,
                returnn_root=MINI_RETURNN_ROOT,
                prefix=prefix + name,
                target="invertibility",
            )
            exp["invertibility_job"] = forward_job
        return exp

    glowTTS_durations_job = tts_exps["glowTTS/enc192/200ep/long_cooldown/not_silence_preprocessed"]["forward_job_joint_durations"]

    train_settings_pe1 = TrainingDatasetSettings(
        custom_processing_function=None, partition_epoch=1, epoch_wise_filters=[], seq_ordering="laplace:.1000"
    )
    training_datasets_pe1_tts_segments = build_training_dataset(
        settings=train_settings_pe1,
        librispeech_key="train-clean-100",
        silence_preprocessing=False,
        use_tts_train_segments=True,
        durations_file=glowTTS_durations_job.out_hdf_files["output.hdf"],
        xvectors_file=x_vector_extractions["x_vector_cnn/1e-3_not_silence_preprocessed"]["hdf"],
    )

    from typing import cast
    from i6_experiments.users.rossenbach.common_setups.returnn.datastreams.vocabulary import LabelDatastream

    label_datastream_asr = cast(LabelDatastream, training_datasets_pe1_tts_segments.datastreams["phonemes_eow"])
    vocab_size_without_blank_asr = label_datastream_asr.vocab_size
    label_datastream_tts = cast(LabelDatastream, training_datasets_pe1_tts_segments.datastreams["phonemes"])
    vocab_size_without_blank_tts = label_datastream_tts.vocab_size
    speaker_datastream = cast(LabelDatastream, training_datasets_pe1_tts_segments.datastreams["speaker_labels"])

    from ..data import get_tts_log_mel_datastream
    from ..feature_config import DbMelFeatureExtractionConfig
    from i6_experiments.users.rossenbach.common_setups.returnn.datastreams.audio import DBMelFilterbankOptions

    log_mel_datastream = get_tts_log_mel_datastream(silence_preprocessing=False)
    log_mel_datastream_silence_preprocessed = get_tts_log_mel_datastream(silence_preprocessing=True)

    assert "norm_mean" in log_mel_datastream.additional_options
    assert "norm_std_dev" in log_mel_datastream.additional_options

    norm = (log_mel_datastream.additional_options["norm_mean"], log_mel_datastream.additional_options["norm_std_dev"])
    assert isinstance(log_mel_datastream.options.feature_options, DBMelFilterbankOptions)
    fe_config = DbMelFeatureExtractionConfig(
        sample_rate=log_mel_datastream.options.sample_rate,
        win_size=log_mel_datastream.options.window_len,
        hop_size=log_mel_datastream.options.step_len,
        f_min=log_mel_datastream.options.feature_options.fmin,
        f_max=log_mel_datastream.options.feature_options.fmax,
        min_amp=log_mel_datastream.options.feature_options.min_amp,
        num_filters=log_mel_datastream.options.num_feature_filters,
        center=log_mel_datastream.options.feature_options.center,
        norm=norm,
    )

    log_mel_datastream_silence_preprocessed = get_tts_log_mel_datastream(silence_preprocessing=True)

    assert "norm_mean" in log_mel_datastream_silence_preprocessed.additional_options
    assert "norm_std_dev" in log_mel_datastream_silence_preprocessed.additional_options

    norm_silence_preprocessed = (
        log_mel_datastream_silence_preprocessed.additional_options["norm_mean"],
        log_mel_datastream_silence_preprocessed.additional_options["norm_std_dev"],
    )
    assert isinstance(log_mel_datastream_silence_preprocessed.options.feature_options, DBMelFilterbankOptions)
    fe_config_silence_preprocessed = DbMelFeatureExtractionConfig(
        sample_rate=log_mel_datastream_silence_preprocessed.options.sample_rate,
        win_size=log_mel_datastream_silence_preprocessed.options.window_len,
        hop_size=log_mel_datastream_silence_preprocessed.options.step_len,
        f_min=log_mel_datastream_silence_preprocessed.options.feature_options.fmin,
        f_max=log_mel_datastream_silence_preprocessed.options.feature_options.fmax,
        min_amp=log_mel_datastream_silence_preprocessed.options.feature_options.min_amp,
        num_filters=log_mel_datastream_silence_preprocessed.options.num_feature_filters,
        center=log_mel_datastream_silence_preprocessed.options.feature_options.center,
        norm=norm_silence_preprocessed,
    )

    tts_forward_datasets = {}
    tts_forward_datasets_xvectors = {}

    tts_forward_datasets["test-clean"] = build_tts_forward_dataset(
        librispeech_key="train-clean-100",
        dataset_key="test-clean",
    )

    tts_forward_datasets_xvectors["test-clean"] = build_tts_forward_dataset(
        librispeech_key="train-clean-100",
        dataset_key="test-clean",
        xvectors_file=x_vector_extractions["x_vector_cnn/1e-3_not_silence_preprocessed/test-clean"]["hdf"],
    )

    asr_test_datasets = {}

    asr_test_datasets["dev-other"] = build_test_dataset(librispeech_key="train-clean-100", dataset_key="dev-other")

    asr_test_datasets2 = copy.deepcopy(asr_test_datasets)
    asr_test_datasets2["train-clean-100-cv"] = build_test_dataset(
        librispeech_key="train-clean-100", dataset_key="train-clean-100", test_on_tts_cv=True
    )
    asr_test_datasets2["dev-clean"] = build_test_dataset(librispeech_key="train-clean-100", dataset_key="dev-clean")

    dev_dataset_tuples_with_phon = {}
    for testset in ["train-clean"]:
        dev_dataset_tuples_with_phon[testset] = (
            training_datasets_pe1_tts_segments.cv,
            get_bliss_corpus_dict()["train-clean-100"],
        )

    text_encoder_config = TextEncoderConfig(
        n_vocab=label_datastream_tts.vocab_size,
        hidden_channels=192,
        filter_channels=768,
        filter_channels_dp=256,
        n_heads=2,
        n_layers=6,
        kernel_size=3,
        p_dropout=0.1,
        window_size=4,
        block_length=None,
        mean_only=False,
        prenet=True,
    )

    flow_decoder_config = FlowDecoderConfig(
        hidden_channels=192,
        kernel_size=5,
        dilation_rate=1,
        n_blocks=12,
        n_layers=4,
        p_dropout=0.05,
        n_split=4,
        n_sqz=2,
        sigmoid_scale=False,
    )

    phoeneme_prediction_config = PhonemePredictionConfig(
        n_channels=512,
        n_layers=3,
        p_dropout=0.1
    )

    model_config = ModelConfigV2(
        specaug_config=None,
        text_encoder_config=text_encoder_config,
        decoder_config=flow_decoder_config,
        phoneme_prediction_config=phoeneme_prediction_config,
        label_target_size=vocab_size_without_blank_tts,
        specauc_start_epoch=1,
        out_channels=80,
        gin_channels=256,
        n_speakers=speaker_datastream.vocab_size,
    )

    model_config_no_dec_drop = copy.deepcopy(model_config)
    model_config_no_dec_drop.decoder_config.p_dropout = 0.0

    net_module = "ga_glowTTS_ASR_ffn_x_vector"

    train_args = {
        "net_args": {"fe_config": asdict(fe_config), "model_config": asdict(model_config)},
        "network_module": net_module,
        "debug": True,
        "config": {
            "optimizer": {"class": "radam", "epsilon": 1e-9},
            "learning_rates": list(np.concatenate((np.linspace(1e-5, 5e-4, 100), np.linspace(5e-4, 1e-5, 100)))),
            "batch_size": 300 * 16000,
            "max_seq_length": {"audio_features": 25 * 16000},
            "max_seqs": 60,
        },
    }

    from typing import cast
    from i6_experiments.users.rossenbach.common_setups.returnn.datastreams.vocabulary import LabelDatastream

    label_datastream = cast(LabelDatastream, training_datasets_pe1_tts_segments.datastreams["phonemes_eow"])

    forward_args = {"noise_scale": 0.66, "length_scale": 1}
    default_search_args = {
        "lexicon": get_text_lexicon(),
        "returnn_vocab": label_datastream.vocab,
        "beam_size": 256,
        "arpa_lm": get_binary_lm(),
        "lm_weight": 5,
        "beam_threshold": 16,
        "asr_data": False,
    }

    x_vect_train_job = x_vector_exp["x_vector_cnn/1e-3_not_silence_preprocessed"]["train_job"]
    train_args["config"]["preload_from_files"] = {
        "x_vector_model": {
            "filename": x_vect_train_job.out_checkpoints[x_vect_train_job.returnn_config.get("num_epochs", 100)],
            "init_for_train": True,
            "prefix": "x_vector.",
            "ignore_missing": True,
        }
    }

    train_args_pretrained_tts = copy.deepcopy(train_args)
    train_args_pretrained_tts["config"]["preload_from_files"] = {
        "glowTTS_xvector": {
            "filename": tts_models["glowTTS_x_vector_v2"].checkpoint,
            "init_for_train": True,
            "ignore_missing": True,
        }
    }

    exp_dict = run_exp(
        net_module + "/200ep/basic_init/ce_ls_0.1",
        train_args,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/200ep/tts_pretrained/ce_ls_0.1",
        train_args_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    net_module = "ga_glowTTS_ASR_ffn_x_vector_v2"
    train_args["network_module"] = net_module
    train_args_pretrained_tts["network_module"] = net_module

    exp_dict = run_exp(
        net_module + "/200ep/basic_init/ce_ls_0.1",
        train_args,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/200ep/tts_pretrained/ce_ls_0.1",
        train_args_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/200ep/basic_init/ce_ls_1.0",
        train_args,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 1.0},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/200ep/tts_pretrained/ce_ls_1.0",
        train_args_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 1.0},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    # ----------------- CNN  -------------------
    net_module = "ga_glowTTS_ASR_cnn_x_vector"
    cnn_phoneme_prediction_config = PhonemePredictionConfigCNN(n_channels=512, n_layers=3, kernel_size=5, p_dropout=0.1)

    model_config_cnn = ModelConfigV2(
        decoder_config=flow_decoder_config,
        text_encoder_config=text_encoder_config,
        label_target_size=vocab_size_without_blank_tts,
        phoneme_prediction_config=cnn_phoneme_prediction_config,
        out_channels=80,
        gin_channels=256,
        n_speakers=speaker_datastream.vocab_size,
    )

    train_args_cnn = copy.deepcopy(train_args)
    train_args_cnn_pretrained_tts = copy.deepcopy(train_args_pretrained_tts)
    train_args_cnn["network_module"] = net_module
    train_args_cnn["net_args"]["model_config"] = asdict(model_config_cnn)
    train_args_cnn_pretrained_tts["network_module"] = net_module
    train_args_cnn_pretrained_tts["net_args"]["model_config"] = asdict(model_config_cnn)

    exp_dict = run_exp(
        net_module + "/basic_init/ce_ls_0.1",
        train_args_cnn,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
    )

    exp_dict = run_exp(
        net_module + "/tts_pretrained/ce_ls_0.1",
        train_args_cnn_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
    )

    net_module = "ga_glowTTS_ASR_cnn_x_vector_v2"
    train_args_cnn["network_module"] = net_module
    train_args_cnn_pretrained_tts["network_module"] = net_module
    exp_dict = run_exp(
        net_module + "/basic_init/ce_ls_0.1",
        train_args_cnn,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/tts_pretrained/ce_ls_0.1",
        train_args_cnn_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.1},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/basic_init/ce_ls_0.01",
        train_args_cnn,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.01},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )

    exp_dict = run_exp(
        net_module + "/tts_pretrained/ce_ls_0.01",
        train_args_cnn_pretrained_tts,
        training_datasets_pe1_tts_segments,
        dev_dataset_tuples_with_phon,
        200,
        forward_args=forward_args,
        training_args={"ce_loss_scale": 0.01},
        search_args=default_search_args,
        tts_eval_datasets=tts_forward_datasets_xvectors,
        encoder_phoneme_pred=True,
    )
