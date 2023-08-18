import copy
import os

from sisyphus import gs, tk

import i6_core.rasr as rasr
from i6_core.returnn.config import CodeWrapper
from i6_core.returnn.config import ReturnnConfig
from i6_experiments.common.baselines.librispeech.ls960.gmm.baseline_config import (
    run_librispeech_960_common_baseline,
)
from i6_experiments.users.berger.args.experiments import hybrid as exp_args
from i6_experiments.users.berger.args.returnn.config import Backend, get_returnn_config
from i6_experiments.users.berger.args.returnn.learning_rates import (
    LearningRateSchedules,
)
from i6_experiments.users.berger.corpus.libri_css.hybrid_data import get_hybrid_data
from i6_experiments.users.berger.network.models import conformer_hybrid_dualchannel
from i6_experiments.users.berger.recipe.converse.scoring import MeetEvalJob
from i6_experiments.users.berger.recipe.summary.report import SummaryReport
from i6_experiments.users.berger.systems.dataclasses import (
    ConfigVariant,
    FeatureType,
    ReturnnConfigs,
)
from i6_experiments.users.berger.systems.functors.rasr_base import LatticeProcessingType
from i6_experiments.users.berger.systems.returnn_legacy_system import (
    ReturnnLegacySystem,
)
from i6_experiments.users.berger.util import default_tools_v2

# ********** Settings **********

rasr.flow.FlowNetwork.default_flags = {"cache_mode": "task_dependent"}

num_outputs = 12001
num_subepochs = 50

tools = copy.deepcopy(default_tools_v2)

# ********** Return Config generators **********


def returnn_config_generator(variant: ConfigVariant, train_data_config: dict, dev_data_config: dict) -> ReturnnConfig:
    extra_config: dict = {
        "train": train_data_config,
        "dev": dev_data_config,
    }
    # if variant == ConfigVariant.RECOG:
    #     extra_config["model_outputs"] = {"classes": {"dim": num_outputs}}
    if variant != ConfigVariant.RECOG:
        extra_config["chunking"] = "400:200"

    if variant == ConfigVariant.RECOG:
        extra_config["extern_data"] = {
            "data": {"dim": 2 * 50},
            "classes": {"dim": num_outputs, "sparse": True},
        }
    else:
        extra_config["__time_tag__"] = CodeWrapper("Dim(dimension=None, kind=Dim.Types.Spatial, description=\"time\")")
        extra_config["extern_data"] = {
            "features_primary": {"dim": 50, "same_dim_tags_as": {"T": CodeWrapper("__time_tag__")}},
            "features_secondary": {"dim": 50, "same_dim_tags_as": {"T": CodeWrapper("__time_tag__")}},
            "classes": {"dim": 1, "dtype": "int32", "same_dim_tags_as": {"T": CodeWrapper("__time_tag__")}},
        }

    if variant == ConfigVariant.TRAIN or variant == ConfigVariant.PRIOR:
        net_dict, extra_python = conformer_hybrid_dualchannel.make_conformer_hybrid_dualchannel_model(
            num_inputs=50,
            num_outputs=num_outputs,
            specaug_args={
                "max_time_num": 20,
                "max_time": 20,
                "max_feature_num": 1,
                "max_feature": 15,
            },
            vgg_args={
                "conv_outputs": [32, 32, 64, 64],
                "conv_strides": [1, 1, 1, 1],
                "max_pool": [1, 2, 1, 1],
                "stack_frames": 3,
                "linear_size": 512,
                "dropout": 0.0,
            },
            conformer_args={
                "size": 512,
                "conv_filter_size": 32,
                "num_att_heads": 8,
                "clipping": 400,
            },
            ff_args_aux={
                "num_layers": 2,
                "size": 256,
                "activation": "relu",
                "dropout": 0.0,
            },
            ff_args_out={
                "num_layers": 0,
            },
            prim_blocks=8,
            sec_blocks=4,
            mas_blocks=4,
            output_args={
                "focal_loss_factor": 2.0,
            },
        )
    else:
        net_dict, extra_python = conformer_hybrid_dualchannel.make_conformer_hybrid_dualchannel_recog_model(
            num_inputs=50,
            num_outputs=num_outputs,
            vgg_args={
                "conv_outputs": [32, 32, 64, 64],
                "conv_strides": [1, 1, 1, 1],
                "max_pool": [1, 2, 1, 1],
                "stack_frames": 3,
                "linear_size": 512,
                "dropout": 0.0,
            },
            conformer_args={
                "size": 512,
                "conv_filter_size": 32,
                "num_att_heads": 8,
                "clipping": 400,
            },
            ff_args_out={
                "num_layers": 0,
            },
            prim_blocks=8,
            sec_blocks=4,
            mas_blocks=4,
        )


    return get_returnn_config(
        network=net_dict,
        num_epochs=num_subepochs,
        num_inputs=50,
        num_outputs=num_outputs,
        target="classes",
        python_prolog=[
            "import sys",
            "sys.setrecursionlimit(10 ** 6)",
            "from returnn.tf.util.data import Dim",
        ],
        extra_python=extra_python,
        extern_data_config=False,
        backend=Backend.TENSORFLOW,
        grad_noise=0.0,
        grad_clip=0.0,
        schedule=LearningRateSchedules.OCLR,
        initial_lr=1e-05,
        peak_lr=3e-04,
        final_lr=1e-06,
        # batch_size=6144,
        batch_size=4000 if variant == ConfigVariant.TRAIN else 1000,
        use_chunking=True,
        extra_config=extra_config,
    )


def get_returnn_config_collection(
    train_data_config: dict,
    dev_data_config: dict,
) -> ReturnnConfigs[ReturnnConfig]:
    generator_kwargs = {
        "train_data_config": train_data_config,
        "dev_data_config": dev_data_config,
    }
    return ReturnnConfigs(
        train_config=returnn_config_generator(variant=ConfigVariant.TRAIN, **generator_kwargs),
        prior_config=returnn_config_generator(variant=ConfigVariant.PRIOR, **generator_kwargs),
        recog_configs={"recog": returnn_config_generator(variant=ConfigVariant.RECOG, **generator_kwargs)},
    )


def run_exp() -> SummaryReport:
    gmm_system = run_librispeech_960_common_baseline(recognition=False)

    assert tools.returnn_root
    assert tools.returnn_python_exe
    assert tools.rasr_binary_path
    data = get_hybrid_data(
        gmm_system=gmm_system,
        returnn_root=tools.returnn_root,
        returnn_python_exe=tools.returnn_python_exe,
        rasr_binary_path=tools.rasr_binary_path,
        lm_name="kazuki_transformer",
        # lm_name="4gram",
    )

    # ********** Step args **********

    train_args = exp_args.get_hybrid_train_step_args(num_epochs=num_subepochs)
    extra_config = rasr.RasrConfig()
    extra_config.flf_lattice_tool.network.recognizer.recognizer.separate_lookahead_lm = True
    recog_args = exp_args.get_hybrid_recog_step_args(
        num_classes=num_outputs,
        epochs=[20, num_subepochs],
        feature_type=FeatureType.CONCAT_GAMMATONE,
        lattice_processing_type=LatticeProcessingType.MultiChannel,
        mem=48,
        rtf=50,
        extra_config=extra_config,
    )

    # ********** System **********

    # tools.rasr_binary_path = tk.Path(
    #     "/u/berger/repositories/rasr_versions/gen_seq2seq_onnx_apptainer/arch/linux-x86_64-standard"
    # )
    system = ReturnnLegacySystem(tools)

    system.init_corpora(
        dev_keys=data.dev_keys,
        test_keys=data.test_keys,
        corpus_data=data.data_inputs,
        am_args=exp_args.get_hybrid_am_args(
            cart_file=gmm_system.outputs["train-other-960"]["final"].crp.acoustic_model_config.state_tying.file
        ),
    )
    system.setup_scoring(
        scorer_type=MeetEvalJob,
        score_kwargs={
            "meet_eval_exe": tk.Path(
                "/work/asr4/vieting/programs/conda/20230126/anaconda3/envs/py310_upb/bin/python3",
                hash_overwrite="MEET_EVAL_EXE",
            )
        },
        stm_path=tk.Path(
            "/work/asr4/vieting/setups/converse/data/ref_libri_css.stm",
            hash_overwrite="libri_css_stm",
        ),
    )

    # ********** Returnn Configs **********

    system.add_experiment_configs(
        "Conformer_Hybrid",
        get_returnn_config_collection(data.train_data_config, data.cv_data_config),
    )

    system.run_train_step(**train_args)
    system.run_dev_recog_step(**recog_args)

    assert system.summary_report
    return system.summary_report


def py() -> SummaryReport:
    filename_handle = os.path.splitext(os.path.basename(__file__))[0][len("config_") :]
    gs.ALIAS_AND_OUTPUT_SUBDIR = f"{filename_handle}/"

    summary_report = SummaryReport()

    summary_report.merge_report(run_exp(), update_structure=True)

    tk.register_report(f"{gs.ALIAS_AND_OUTPUT_SUBDIR}/summary.report", summary_report)

    return summary_report
