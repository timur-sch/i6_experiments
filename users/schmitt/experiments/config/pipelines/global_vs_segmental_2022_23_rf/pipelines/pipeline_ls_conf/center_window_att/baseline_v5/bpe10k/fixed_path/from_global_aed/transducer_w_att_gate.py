from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.center_window_att.baseline_v5 import (
  get_config_builder,
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.center_window_att import (
  train, recog, realign
)

from i6_core.returnn.training import PtCheckpoint
from sisyphus import Path


def run_exps():
  # ------------------- Transducer + global att in Readout + gate ---------------------

  # ------------------- prev att not in state ---------------------
  for model_alias, config_builder in get_config_builder.center_window_att_baseline_rf(
          win_size_list=(None,),
          blank_decoder_version=4,
          use_att_ctx_in_state=False,
          use_weight_feedback=False,
          use_current_frame_in_readout_w_gate=True,
  ):
    for train_alias, checkpoint in train.train_center_window_att_viterbi_import_global_tf(
            alias=model_alias,
            config_builder=config_builder,
            n_epochs_list=(300,),
            const_lr_list=(1e-4,),
            batch_size=10_000,
    ):
      recog.center_window_returnn_frame_wise_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
      )
      recog.center_window_returnn_frame_wise_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=("last",),
        run_analysis=True,
        analyze_gradients=True,
      )

  # ------------------- prev att in state ---------------------
  for model_alias, config_builder in get_config_builder.center_window_att_baseline_rf(
          win_size_list=(None,),
          blank_decoder_version=4,
          use_att_ctx_in_state=True,
          use_weight_feedback=False,
          use_current_frame_in_readout_w_gate=True,
  ):
    for train_alias, checkpoint in train.train_center_window_att_viterbi_import_global_tf(
            alias=model_alias,
            config_builder=config_builder,
            n_epochs_list=(300,),
            const_lr_list=(1e-4,),
            batch_size=10_000,
    ):
      recog.center_window_returnn_frame_wise_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
      )
      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch % 50 == 0 and epoch not in (50, 200):
          recog.center_window_returnn_frame_wise_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
          )
