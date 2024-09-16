from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att.baseline_v2 import (
  baseline
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att import (
  train, recog
)


def run_exps():
  for model_alias, config_builder in baseline.global_att_baseline_rf(
    use_weight_feedback=True,
    label_type="bpe1056",
  ):
    for gpu_mem_rqmt in [
      11,
      # 24
    ]:
      if gpu_mem_rqmt == 24:
        use_mgpu = False
        accum_grad_multiple_step = 2
        batch_size = 35_000
        n_epochs = 2_000
      else:
        use_mgpu = True
        accum_grad_multiple_step = 4
        batch_size = 15_000
        n_epochs = 500

      for train_alias, checkpoint in train.train_global_att(
              alias=model_alias,
              config_builder=config_builder,
              n_epochs=n_epochs,
              batch_size=batch_size,
              keep_epochs=list(range(240)),
              lr_scheduling_type="dyn_lr_piecewise_linear_epoch-wise_v2",
              gpu_mem_rqmt=gpu_mem_rqmt,
              accum_grad_multiple_step=accum_grad_multiple_step,
              use_mgpu=use_mgpu,
              use_torch_amp=False,
              filter_data_len=19.5 * 16_000,
      ):
        recog.global_att_returnn_label_sync_beam_search(
          alias=train_alias,
          config_builder=config_builder,
          checkpoint=checkpoint,
        )

        analysis_epochs = range(10, 240, 10)

        for epoch, chckpt in checkpoint["checkpoints"].items():
          if epoch in analysis_epochs:
            recog.global_att_returnn_label_sync_beam_search(
              alias=train_alias,
              config_builder=config_builder,
              checkpoint=chckpt,
              checkpoint_aliases=(f"epoch-{epoch}",),
              run_analysis=True,
              analyze_gradients=True,
              only_do_analysis=True,
            )





