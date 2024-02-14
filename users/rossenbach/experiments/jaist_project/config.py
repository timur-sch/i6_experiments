"""
Universal helpers to create configuration objects (i6_core ReturnnConfig) for RETURNN training/forwarding
"""
import copy
from typing import Any, Dict, Optional

from i6_core.returnn.config import ReturnnConfig, CodeWrapper

from i6_experiments.common.setups.returnn_pytorch.serialization import (
    Collection as TorchCollection,
)
from i6_experiments.common.setups.serialization import Import
from .data.common import TrainingDatasets
from .serializer import get_pytorch_serializer_v3, PACKAGE


def get_training_config(
        training_datasets: TrainingDatasets,
        network_module: str,
        net_args: Dict[str, Any],
        config: Dict[str, Any],
        debug: bool = False,
        use_custom_engine: bool = False,
        use_speed_perturbation: bool = False,
        post_config: Optional[Dict[str, Any]] = None,
) -> ReturnnConfig:
    """
    Get a generic config for training a model

    :param training_datasets: datasets for training
    :param network_module: path to the pytorch config file containing Model
    :param net_args: extra arguments for constructing the PyTorch model
    :param config: config arguments for RETURNN
    :param debug: run training in debug mode (linking from recipe instead of copy)
    :param use_custom_engine: link custom engine source code (for RETURNN) from the specified network module
    :param use_speed_perturbation: Use speedperturbation in the training
    :param post_config: Add non-hashed arguments for RETURNN
    """

    # changing these does not change the hash
    base_post_config = {
        "cleanup_old_models": True,
        "stop_on_nonfinite_train_score": True,
        "num_workers_per_gpu": 2,
        "backend": "torch"
    }

    base_config = {
        #############
        "train": copy.deepcopy(training_datasets.train.as_returnn_opts()),
        "dev": training_datasets.cv.as_returnn_opts(),
        "eval_datasets": {
            "devtrain": training_datasets.devtrain.as_returnn_opts()
        }
    }
    config = {**base_config, **copy.deepcopy(config)}
    post_config = {**base_post_config, **copy.deepcopy(post_config or {})}

    serializer = get_pytorch_serializer_v3(
        network_module=network_module,
        net_args=net_args,
        debug=debug,
        use_custom_engine=use_custom_engine
    )
    python_prolog = None

    # TODO: maybe make nice
    if use_speed_perturbation:
        prolog_serializer = TorchCollection(
            serializer_objects=[Import(
                code_object_path=PACKAGE + ".extra_code.speed_perturbation.legacy_speed_perturbation",
                unhashed_package_root=PACKAGE
            )]
        )
        python_prolog = [prolog_serializer]
        config["train"]["datasets"]["zip_dataset"]["audio"]["pre_process"] = CodeWrapper("legacy_speed_perturbation")

    returnn_config = ReturnnConfig(
        config=config, post_config=post_config, python_prolog=python_prolog, python_epilog=[serializer]
    )
    return returnn_config


def get_prior_config(
        training_datasets: TrainingDatasets,
        network_module: str,
        net_args: Dict[str, Any],
        config: Dict[str, Any],
        debug: bool = False,
        use_custom_engine: bool = False,
        **kwargs,
):
    """
     Get a generic config for extracting output label priors

     :param training_datasets: datasets for training
     :param network_module: path to the pytorch config file containing Model
     :param net_args: extra arguments for constructing the PyTorch model
     :param config: config arguments for RETURNN
     :param debug: run training in debug mode (linking from recipe instead of copy)
     :param use_custom_engine: link custom engine source code (for RETURNN) from the specified network module
    """

    # changing these does not change the hash
    post_config = {
    }

    base_config = {
        #############
        "batch_size": 2000 * 16000,
        "max_seqs": 240,
        #############
        "forward": training_datasets.prior.as_returnn_opts()

    }
    config = {**base_config, **copy.deepcopy(config)}
    post_config["backend"] = "torch"

    serializer = get_pytorch_serializer_v3(
        network_module=network_module,
        net_args=net_args,
        debug=debug,
        use_custom_engine=use_custom_engine,
        prior=True,
    )
    returnn_config = ReturnnConfig(
        config=config, post_config=post_config, python_epilog=[serializer]
    )
    return returnn_config


def get_forward_config(
        network_module: str,
        net_args: Dict[str, Any],
        decoder: str,
        decoder_args: Dict[str, Any],
        config: Dict[str, Any],
        debug: bool = False,
        use_custom_engine: bool = False,
        **kwargs,
) -> ReturnnConfig:
    """
     Get a generic config for forwarding

     :param network_module: path to the pytorch config file containing Model
     :param net_args: extra arguments for constructing the PyTorch model
     :param decoder: which (python) file to load which defines the forward, forward_init and forward_finish functions
     :param decoder_args: extra arguments to pass to forward_init
     :param config: config arguments for RETURNN
     :param debug: run training in debug mode (linking from recipe instead of copy)
     :param use_custom_engine: link custom engine source code (for RETURNN) from the specified network module
    """

    # changing these does not change the hash
    post_config = {
    }

    # changeing these does change the hash
    base_config = {
        "batch_size": 1000 * 16000,
        "max_seqs": 240,
    }
    config = {**base_config, **copy.deepcopy(config)}
    post_config["backend"] = "torch"

    serializer = get_pytorch_serializer_v3(
        network_module=network_module,
        net_args=net_args,
        debug=debug,
        use_custom_engine=use_custom_engine,
        decoder=decoder,
        decoder_args=decoder_args,
    )
    returnn_config = ReturnnConfig(
        config=config, post_config=post_config, python_epilog=[serializer]
    )
    return returnn_config
