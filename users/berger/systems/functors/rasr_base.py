from abc import ABC
from typing import Union, Optional

from i6_core import features, rasr, recognition, returnn
from i6_experiments.users.berger.recipe import returnn as custom_returnn
from i6_experiments.users.berger.util import ToolPaths, lru_cache_with_signature
from i6_experiments.users.berger import helpers
from sisyphus import tk

from .. import dataclasses
from .. import types


class RasrFunctor(ABC):
    def __init__(
        self,
        returnn_root: tk.Path,
        returnn_python_exe: tk.Path,
        blas_lib: Optional[tk.Path] = None,
    ) -> None:
        self.returnn_root = returnn_root
        self.returnn_python_exe = returnn_python_exe
        self.blas_lib = blas_lib

    @staticmethod
    def _is_autoregressive_decoding(label_scorer_type: str) -> bool:
        return label_scorer_type != "precomputed-log-posterior"

    @lru_cache_with_signature
    def _get_epoch_value(
        self, train_job: returnn.ReturnnTrainingJob, epoch: types.EpochType
    ) -> Union[int, tk.Variable]:
        if epoch == "best":
            return custom_returnn.GetBestEpochJob(train_job.out_learning_rates).out_epoch
        return epoch

    @lru_cache_with_signature
    def _get_epoch_string(self, epoch: types.EpochType) -> str:
        if isinstance(epoch, str):
            return epoch
        return f"{epoch:03d}"

    def _make_tf_graph(
        self,
        train_job: returnn.ReturnnTrainingJob,
        returnn_config: returnn.ReturnnConfig,
        epoch: types.EpochType,
        label_scorer_type: str = "precomputed-log-posterior",
    ) -> tk.Path:
        rec_step_by_step = "output" if self._is_autoregressive_decoding(label_scorer_type) else None
        graph_compile_job = returnn.CompileTFGraphJob(
            returnn_config,
            returnn_root=self.returnn_root,
            returnn_python_exe=self.returnn_python_exe,
            epoch=self._get_epoch_value(train_job, epoch),
            rec_step_by_step=rec_step_by_step,
            rec_json_info=bool(rec_step_by_step),
        )
        return graph_compile_job.out_graph

    def _make_onnx_model(
        self,
        returnn_config: returnn.ReturnnConfig,
        checkpoint: returnn.PtCheckpoint,
    ) -> tk.Path:
        onnx_export_job = custom_returnn.ExportPyTorchModelToOnnxJob(
            pytorch_checkpoint=checkpoint,
            returnn_config=returnn_config,
            returnn_root=self.returnn_root,
        )
        return onnx_export_job.out_onnx_model

    def _make_base_feature_flow(self, corpus_info: dataclasses.CorpusInfo, **kwargs):
        audio_format = corpus_info.data.corpus_object.audio_format
        args = {
            "audio_format": audio_format,
            "dc_detection": False,
            "input_options": {"block-size": 1},
            "scale_input": 2**-15,
        }
        args.update(kwargs)
        return features.samples_flow(**args)

    @lru_cache_with_signature
    def _get_checkpoint(
        self,
        train_job: returnn.ReturnnTrainingJob,
        epoch: types.EpochType,
    ) -> types.CheckpointType:
        if epoch == "best":
            return custom_returnn.GetBestCheckpointJob(
                model_dir=train_job.out_model_dir,
                learning_rates=train_job.out_learning_rates,
                backend=custom_returnn.get_backend(train_job.returnn_config),
            ).out_checkpoint
        return train_job.out_checkpoints[epoch]

    def _get_prior_file(
        self,
        prior_config: returnn.ReturnnConfig,
        checkpoint: types.CheckpointType,
        **kwargs,
    ) -> tk.Path:
        prior_job = returnn.ReturnnComputePriorJobV2(
            model_checkpoint=checkpoint,
            returnn_config=prior_config,
            returnn_root=self.returnn_root,
            returnn_python_exe=self.returnn_python_exe,
            **kwargs,
        )

        prior_job.update_rqmt("run", {"file_size": 150})

        return prior_job.out_prior_xml_file

    @lru_cache_with_signature
    def _get_native_lstm_op(self) -> tk.Path:
        tools = ToolPaths(
            returnn_root=self.returnn_root,
            returnn_python_exe=self.returnn_python_exe,
            blas_lib=self.blas_lib,
        )
        return helpers.get_native_lstm_op(tools)

    def _make_tf_feature_flow(
        self,
        base_flow: rasr.FlowNetwork,
        tf_graph: tk.Path,
        tf_checkpoint: returnn.Checkpoint,
        output_layer_name: str = "output",
    ) -> rasr.FlowNetwork:
        # tf flow (model scoring done in tf flow node) #
        input_name = "tf-fwd_input"

        tf_flow = rasr.FlowNetwork()
        tf_flow.add_input(input_name)
        tf_flow.add_output("features")
        tf_flow.add_param("id")

        tf_fwd = tf_flow.add_node("tensorflow-forward", "tf-fwd", {"id": "$(id)"})
        tf_flow.link(f"network:{input_name}", f"{tf_fwd}:input")
        tf_flow.link(f"{tf_fwd}:log-posteriors", "network:features")

        tf_flow.config = rasr.RasrConfig()  # type: ignore
        tf_flow.config[tf_fwd].input_map.info_0.param_name = "input"  # type: ignore
        tf_flow.config[tf_fwd].input_map.info_0.tensor_name = "extern_data/placeholders/data/data"  # type: ignore
        tf_flow.config[
            tf_fwd
        ].input_map.info_0.seq_length_tensor_name = "extern_data/placeholders/data/data_dim0_size"  # type: ignore

        tf_flow.config[tf_fwd].output_map.info_0.param_name = "log-posteriors"  # type: ignore
        tf_flow.config[tf_fwd].output_map.info_0.tensor_name = f"{output_layer_name}/output_batch_major"  # type: ignore

        tf_flow.config[tf_fwd].loader.type = "meta"  # type: ignore
        tf_flow.config[tf_fwd].loader.meta_graph_file = tf_graph  # type: ignore
        tf_flow.config[tf_fwd].loader.saved_model_file = tf_checkpoint  # type: ignore

        tf_flow.config[tf_fwd].loader.required_libraries = self._get_native_lstm_op()  # type: ignore

        # interconnect flows #
        ext_flow = rasr.FlowNetwork()
        base_mapping = ext_flow.add_net(base_flow)
        tf_mapping = ext_flow.add_net(tf_flow)
        ext_flow.interconnect_inputs(base_flow, base_mapping)
        ext_flow.interconnect(
            base_flow,
            base_mapping,
            tf_flow,
            tf_mapping,
            {list(base_flow.outputs)[0]: input_name},
        )

        ext_flow.interconnect_outputs(tf_flow, tf_mapping)
        # ensure cache_mode as base feature net
        ext_flow.add_flags(base_flow.flags)
        return ext_flow

    def _make_onnx_feature_flow(
        self,
        base_flow: rasr.FlowNetwork,
        onnx_model: tk.Path,
    ) -> rasr.FlowNetwork:
        # tf flow (model scoring done in tf flow node) #
        input_name = "onnx-fwd_input"

        onnx_flow = rasr.FlowNetwork()
        onnx_flow.add_input(input_name)
        onnx_flow.add_output("features")
        onnx_flow.add_param("id")

        onnx_fwd = onnx_flow.add_node("onnx-forward", "onnx-fwd", {"id": "$(id)"})
        onnx_flow.link(f"network:{input_name}", f"{onnx_fwd}:input")
        onnx_flow.link(f"{onnx_fwd}:log-posteriors", "network:features")

        onnx_flow.config = rasr.RasrConfig()  # type: ignore
        onnx_flow.config[onnx_fwd].io_map.features = "data"
        onnx_flow.config[onnx_fwd].io_map.output = "classes"

        onnx_flow.config[onnx_fwd].session.file = onnx_model
        onnx_flow.config[onnx_fwd].session.inter_op_num_threads = 2
        onnx_flow.config[onnx_fwd].session.intra_op_num_threads = 2

        # interconnect flows #
        ext_flow = rasr.FlowNetwork()
        base_mapping = ext_flow.add_net(base_flow)
        tf_mapping = ext_flow.add_net(onnx_flow)
        ext_flow.interconnect_inputs(base_flow, base_mapping)
        ext_flow.interconnect(
            base_flow,
            base_mapping,
            onnx_flow,
            tf_mapping,
            {list(base_flow.outputs)[0]: input_name},
        )

        ext_flow.interconnect_outputs(onnx_flow, tf_mapping)
        # ensure cache_mode as base feature net
        ext_flow.add_flags(base_flow.flags)
        return ext_flow

    def _lattice_scoring(
        self,
        crp: rasr.CommonRasrParameters,
        lattice_bundle: tk.Path,
        scorer: dataclasses.ScorerInfo,
        **kwargs,
    ) -> types.ScoreJob:
        lat2ctm = recognition.LatticeToCtmJob(
            crp=crp,
            lattice_cache=lattice_bundle,
            **kwargs,
        )

        score_job = scorer.get_score_job(lat2ctm.out_ctm_file)

        return score_job
