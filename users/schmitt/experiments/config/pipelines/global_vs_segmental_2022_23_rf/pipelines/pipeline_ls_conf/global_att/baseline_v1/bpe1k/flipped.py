from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att.baseline_v1 import (
  baseline
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att import (
  train, recog
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.checkpoints import external_checkpoints, default_import_model_name
import os
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23.dependencies.labels.v2.librispeech.phonemes.gmm_alignments import LIBRISPEECH_GMM_WORD_ALIGNMENT
from i6_experiments.users.schmitt.visualization.visualization import PlotAttentionWeightsJobV2, PlotSelfAttentionWeightsOverEpochsJob

from sisyphus import Path, tk


def run_exps():
  for (
          alias,
          random_seed,
          disable_self_att_until_epoch,
          ctc_aux_loss_layers,
          conformer_wo_final_layer_norm_per_layer,
          conformer_num_layers,
          conformer_out_dim,
          conformer_wo_convolution,
          conformer_wo_rel_pos_enc,
          conformer_w_abs_pos_enc,
          keep_epochs,
          gpu_mem_rqmt,
          enc_ctx_layer,
          hard_att_opts,
          conformer_conv_w_zero_padding,
          use_feed_forward_encoder,
          conv_frontend_w_zero_padding,
          cutoff_initial_silence,
          use_speed_pert_w_flip,
  ) in [
    # ["v3_big", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 24], # v3_big: same as v2, but on 24gb GPU with batch size 40k
    ["v3_rand-9999", 9999, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v3_big_rand - flipped
    ["v3_rand-1234", 1234, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v3_big_rand -
    ["v3_rand-1111", 1111, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v3_rand-4321", 4321, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v3_rand-5678", 5678, None, None, False, 12, 512, False, False, False, list(range(10, 80, 10)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v3_rand-8765", 8765, None, None, False, 12, 512, False, False, False, list(range(10, 80, 10)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v3_rand-2222", 2222, None, None, False, 12, 512, False, False, False, list(range(10, 80, 10)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v3_rand-3333", 3333, None, None, False, 12, 512, False, False, False, list(range(10, 80, 10)), 11, None, None, False, False, False, False, False],  # v3_big_rand
    ["v5", None, 21, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v5_big: same as v3_big, but enable self attention only after 20 sub-epochs (1 full epoch)
    ["v6_big", None, None, None, False, 12, 512, False, False, True, list(range(1, 240)), 24, None, None, False, False, False, False, False],  # v6_big: same as v3_big, but use both absolute and relative positional encodings
    ["v6", None, None, None, False, 12, 512, False, False, True, list(range(1, 240)), 11, None, None, False, False, False, False, False], # v6_big: same as v3_big, but use both absolute and relative positional encodings
    # ["v7_big", None, None, None, True, 12, 512, False, False, False, [121, 131, 141], 24, None, None, False],  # v7_big: same as v3_big, but do not use final layer norm in conformer encoder layers
    ["v7", None, None, None, True, 12, 512, False, False, False, [121, 131, 141], 11, None, None, False, False, False, False, False],  # v7: same as v3_big, but do not use final layer norm in conformer encoder layers
    ["v8", None, None, (4, 8), False, 12, 512, False, False, False, list(range(1, 141, 10)), 11, None, None, False, False, False, False, False],  # v8_big: same as v3_big, but use CTC aux loss
    # ["v9_big", None, None, None, False, 17, 400, False, False, False, list(range(1, 240)), 24, None, None, False],  # v9_big: same as v3_big, but use 17 instead of 12 encoder layers and 400 instead of 512 output dim
    ["v9", None, None, None, False, 17, 400, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False], # v9: same as v3_big, but use 17 instead of 12 encoder layers and 400 instead of 512 output dim
    ["v9_rand-1234", 1234, None, None, False, 17, 400, False, False, False, list(range(1, 122)), 11, None, None, False, False, False, False, False],  # v9: same as v3_big, but use 17 instead of 12 encoder layers and 400 instead of 512 output dim
    ["v10", None, None, None, False, 12, 512, True, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, False], # v10_big: same as v3_big, but without convolution module in conformer encoder layers
    # ["v11_big", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 24, "encoder_input", None, False], # v11_big: same as v3_big, but use encoder input as att keys
    ["v11", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, "encoder_input", None, False, False, False, False, False],  # v11_big: same as v3_big, but use encoder input as att keys
    # ["v12_big", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 24, None, {"frame": "middle", "until_epoch": 100, "num_interpolation_epochs": 20}, False], # v12_big: same as v3_big, but use hard att on center frame until sub-epoch 100
    ["v12", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, {"frame": "middle", "until_epoch": 100, "num_interpolation_epochs": 20}, False, False, False, False, False],  # v12_big: same as v3_big, but use hard att on center frame until sub-epoch 100
    ["v13", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, True, False, False, False, False], # v13: same as v3_big, but set padding to zero before depthwise conv in conformer encoder layers
    # ["v14", None, None, None, False, 6, 512, False, False, False, list(range(1, 240)), 11, None, None, False, True, False, False, False],  # v14: same as v3_big, but use FF encoder with 6 layers -> not converged
    ["v15", None, None, None, False, 12, 512, False, True, False, list(range(1, 240)), 11, None, None, False, False, False, False, False],  # v15: same as v3, but without pos encoding
    ["v16", None, None, None, False, 12, 512, False, False, False, list(range(1, 120)), 11, None, None, True, False, True, False, False],  # v16: same as v3, but set padding to zero before depthwise conv in conformer encoder layers and before conv in frontend
    ["v17", None, None, None, False, 12, 512, False, False, False, list(range(1, 120)), 11, None, None, False, False, False, True, False],  # v17: same as v3, but cut off initial silence
    ["v18", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, {"frame": "5", "until_epoch": 100, "num_interpolation_epochs": 20}, False, False, False, False, False], # v12_big: same as v3_big, but use hard att on center frame until sub-epoch 100
    ["v19", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 11, None, None, False, False, False, False, True],  # v19: same as v3 but reverse audio
  ]:
    for model_alias, config_builder in baseline.global_att_baseline_rf(
            use_weight_feedback=True,
            label_type="bpe1056",
            conformer_wo_final_layer_norm_per_layer=conformer_wo_final_layer_norm_per_layer,
            conformer_num_layers=conformer_num_layers,
            conformer_out_dim=conformer_out_dim,
            conformer_wo_convolution=conformer_wo_convolution,
            conformer_wo_rel_pos_enc=conformer_wo_rel_pos_enc,
            conformer_w_abs_pos_enc=conformer_w_abs_pos_enc,
            enc_ctx_layer=enc_ctx_layer,
            conformer_conv_w_zero_padding=conformer_conv_w_zero_padding,
            use_feed_forward_encoder=use_feed_forward_encoder,
            hard_att_opts=hard_att_opts,
            conv_frontend_w_zero_padding=conv_frontend_w_zero_padding,
    ):
      if alias == "v8":
        use_mgpu = False
        accum_grad_multiple_step = 4
        batch_size = 15_000
        n_epochs = 500
      else:
        if gpu_mem_rqmt == 24:
          use_mgpu = False
          accum_grad_multiple_step = 2
          batch_size = 30_000 if alias == "v9_big" else 35_000
          n_epochs = 2_000
        else:
          use_mgpu = True
          accum_grad_multiple_step = 4
          batch_size = 12_000 if alias == "v9" else 15_000
          n_epochs = 500

      for train_alias, checkpoint in train.train_global_att(
              alias=model_alias,
              config_builder=config_builder,
              n_epochs=n_epochs,
              batch_size=batch_size,
              keep_epochs=keep_epochs,
              gpu_mem_rqmt=gpu_mem_rqmt,
              accum_grad_multiple_step=accum_grad_multiple_step,
              use_mgpu=use_mgpu,
              use_torch_amp=False,
              filter_data_len=19.5 * 16_000,
              random_seed=random_seed,
              disable_enc_self_att_until_epoch=disable_self_att_until_epoch,
              ctc_aux_loss_layers=ctc_aux_loss_layers,
              hard_att_opts=hard_att_opts,
              cutoff_initial_silence=cutoff_initial_silence,
              use_speed_pert_w_flip=use_speed_pert_w_flip,
      ):
        recog.global_att_returnn_label_sync_beam_search(
          alias=train_alias,
          config_builder=config_builder,
          checkpoint=checkpoint,
          corpus_keys=("dev-other",)
        )

        analysis_epochs = [121, 131]
        # if alias in ("v3_big", "v3_big_rand-1337", "v5_big", "v6_big", "v11", "v11_big"):
        analysis_epochs += list(range(1, 141, 10))
        if alias in ("v3_big", "v3_big_rand-1337"):
          analysis_epochs += list(range(90, 141))
        if alias in ("v11", "v11_big"):
          analysis_epochs += [1, 5]
        if alias == "v10_big":
          analysis_epochs += [190, 230, 396]
        if alias == "v7":
          analysis_epochs += [191]
        if alias == "v10":
          analysis_epochs += [200]
        if alias == "v7":
          analysis_epochs += [500]

        only_do_analysis = True

        for epoch, chckpt in checkpoint["checkpoints"].items():
          if alias == "v11" and epoch in [131]:
            only_do_analysis = False

          if epoch in analysis_epochs:
            recog.global_att_returnn_label_sync_beam_search(
              alias=train_alias,
              config_builder=config_builder,
              checkpoint=chckpt,
              checkpoint_aliases=(f"epoch-{epoch}",),
              run_analysis=True,
              analyze_gradients=True,
              only_do_analysis=only_do_analysis,
            )

          if epoch in [61, 225] and alias == "v16":
            if epoch == 61:
              input_layer_names = ["encoder_input", "frontend_input"]
            else:
              input_layer_names = ["frontend_input"]
            for input_layer_name in input_layer_names:
              recog.global_att_returnn_label_sync_beam_search(
                alias=train_alias,
                config_builder=config_builder,
                checkpoint=chckpt,
                checkpoint_aliases=(f"epoch-{epoch}",),
                run_analysis=True,
                analysis_dump_gradients=True,
                only_do_analysis=True,
                corpus_keys=("train",),
                att_weight_seq_tags=None,
                analysis_dump_gradients_input_layer_name=input_layer_name,
              )

          if (alias == "v3_rand-4321" and epoch in [
            10,
            20, 30, 40, 50, 60
          ]) or (alias == "v8" and epoch in [11, 21, 31, 41, 51, 61]) or (
            alias == "v3_rand-9999" and epoch in [10, 20, 30, 40, 50, 60, 70, 80]
          ) or (alias == "v6" and epoch in list(range(51)) + [60]):
            seq_tags = []
            if alias == "v3_rand-9999" or (alias == "v8" and epoch == 61):
              seq_tags.append("train-other-960/1246-124548-0042/1246-124548-0042")
            else:
              seq_tags.append("train-other-960/1578-6379-0013/1578-6379-0013")

            recog.global_att_returnn_label_sync_beam_search(
              alias=train_alias,
              config_builder=config_builder,
              checkpoint=chckpt,
              checkpoint_aliases=(f"epoch-{epoch}",),
              corpus_keys=("train",),
              run_analysis=True,
              analyze_gradients=True,
              only_do_analysis=True,
              att_weight_seq_tags=seq_tags,
              analysis_ref_alignment_opts={
                "ref_alignment_hdf": LIBRISPEECH_GMM_WORD_ALIGNMENT.alignment_paths["train"],
                "ref_alignment_blank_idx": LIBRISPEECH_GMM_WORD_ALIGNMENT.model_hyperparameters.blank_idx,
                "ref_alignment_vocab_path": LIBRISPEECH_GMM_WORD_ALIGNMENT.vocab_path,
              },
              analysis_analyze_gradients_plot_encoder_layers=True,
              analsis_analyze_gradients_plot_log_gradients=True,
            )

          if (alias == "v6" and epoch in [10, 20, 30, 40, 50, 60] + list(range(20, 51))):
            seq_tags_list = [["train-other-960/40-222-0033/40-222-0033"]]
            if epoch in [40, 45]:
              seq_tags_list += [
                [
                  "train-other-960/103-1240-0038/103-1240-0038",
                  "train-other-960/103-1240-0057/103-1240-0057",
                  "train-other-960/103-1241-0019/103-1241-0019",
                  "train-other-960/103-1241-0025/103-1241-0025",
                  "train-other-960/103-1241-0043/103-1241-0043",
                  "train-other-960/1034-121119-0013/1034-121119-0013",
                ]
              ]
            if epoch in [60]:
              seq_tags_list += [["train-other-960/1246-124548-0042/1246-124548-0042"]]
            for seq_tags in seq_tags_list:
              recog.global_att_returnn_label_sync_beam_search(
                alias=train_alias,
                config_builder=config_builder,
                checkpoint=chckpt,
                checkpoint_aliases=(f"epoch-{epoch}",),
                corpus_keys=("train",),
                run_analysis=True,
                analyze_gradients=True,
                only_do_analysis=True,
                att_weight_seq_tags=seq_tags,
                analysis_ref_alignment_opts={
                  "ref_alignment_hdf": LIBRISPEECH_GMM_WORD_ALIGNMENT.alignment_paths["train"],
                  "ref_alignment_blank_idx": LIBRISPEECH_GMM_WORD_ALIGNMENT.model_hyperparameters.blank_idx,
                  "ref_alignment_vocab_path": LIBRISPEECH_GMM_WORD_ALIGNMENT.vocab_path,
                },
                analysis_analyze_gradients_plot_encoder_layers=True,
                analsis_analyze_gradients_plot_log_gradients=epoch in [10, 60],
                analysis_dump_self_att=epoch in [10, 20, 30, 40, 50, 60],
              )

          if (alias == "v8" and epoch == 61):
            for seq_tags in [["train-other-960/40-222-0033/40-222-0033"]]:
              recog.global_att_returnn_label_sync_beam_search(
                alias=train_alias,
                config_builder=config_builder,
                checkpoint=chckpt,
                checkpoint_aliases=(f"epoch-{epoch}",),
                corpus_keys=("train",),
                run_analysis=True,
                analyze_gradients=True,
                only_do_analysis=True,
                att_weight_seq_tags=seq_tags,
                analysis_ref_alignment_opts={
                  "ref_alignment_hdf": LIBRISPEECH_GMM_WORD_ALIGNMENT.alignment_paths["train"],
                  "ref_alignment_blank_idx": LIBRISPEECH_GMM_WORD_ALIGNMENT.model_hyperparameters.blank_idx,
                  "ref_alignment_vocab_path": LIBRISPEECH_GMM_WORD_ALIGNMENT.vocab_path,
                },
                analysis_analyze_gradients_plot_encoder_layers=False,
                analsis_analyze_gradients_plot_log_gradients=False,
                analysis_dump_self_att=False,
              )

        # if gpu_mem_rqmt == 24:
        #   all_epochs = range(2000, 0, -1)
        # else:
        #   all_epochs = range(500, 0, -1)
        #
        # for epoch in all_epochs:
        #   chckpt = checkpoint["checkpoints"][epoch]
        #
        #   if os.path.exists(chckpt.path):
        #     recog.global_att_returnn_label_sync_beam_search(
        #       alias=train_alias,
        #       config_builder=config_builder,
        #       checkpoint=chckpt,
        #       checkpoint_aliases=(f"epoch-{epoch}",),
        #       corpus_keys=("train",),
        #       run_analysis=True,
        #       analyze_gradients=True,
        #       only_do_analysis=True,
        #       att_weight_seq_tags=["train-other-960/1578-6379-0013/1578-6379-0013"],
        #       analysis_ref_alignment_opts={
        #         "ref_alignment_hdf": LIBRISPEECH_GMM_WORD_ALIGNMENT.alignment_paths["train"],
        #         "ref_alignment_blank_idx": LIBRISPEECH_GMM_WORD_ALIGNMENT.model_hyperparameters.blank_idx,
        #         "ref_alignment_vocab_path": LIBRISPEECH_GMM_WORD_ALIGNMENT.vocab_path,
        #       }
        #     )
        #     break  # only do this for the first existing checkpoint

  # plot_flipped_cross_att_weight_evolution()
  # plot_flipped_self_att_weight_evolution()
  # plot_flipped_vs_normal_cross_att_weights()
  # plot_gradients_wrt_different_layers()


def plot_flipped_cross_att_weight_evolution():
  epochs = [
    10,
    # 20,
    # 30,
    # 32,
    # 34,
    # 36,
    # 38,
    40,
    45,
    50,
    # 60
  ]
  plot_att_weights_job = PlotAttentionWeightsJobV2(
    att_weight_hdf=[
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-{epoch}-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/cross-att/enc-layer-12/att_weights/att_weights.hdf") for epoch in epochs
    ],
    targets_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-50-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/output/targets.hdf"),
    seg_starts_hdf=None,
    seg_lens_hdf=None,
    center_positions_hdf=None,
    target_blank_idx=None,
    ref_alignment_blank_idx=0,
    ref_alignment_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_hdf_align.hdf"),
    json_vocab_path=Path("/work/asr4/zeineldeen/setups-data/librispeech/2022-11-28--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.qhkNn2veTWkV/output/bpe.vocab"),
    ctc_alignment_hdf=None,
    segment_whitelist=["train-other-960/40-222-0033/40-222-0033"],
    ref_alignment_json_vocab_path=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_vocab"),
    plot_w_cog=False,
    titles=[f"Epoch {epoch * 4 / 20}" for epoch in epochs],
    # titles=[f"Epoch {epoch * 4 // 20 if (epoch * 4 / 20).is_integer() else epoch * 4 / 20}" for epoch in epochs],
  )
  plot_att_weights_job.add_alias(f"flipped_cross_att_evolution")
  tk.register_output(plot_att_weights_job.get_one_alias(), plot_att_weights_job.out_plot_dir)


def plot_flipped_vs_normal_cross_att_weights():
  plot_att_weights_job = PlotAttentionWeightsJobV2(
    att_weight_hdf=[
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/cross-att/enc-layer-12/att_weights/att_weights.hdf"),
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_standard-conformer/train_from_scratch/500-ep_bs-15000_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4_ce-aux-4-8/returnn_decoding/epoch-61-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/cross-att/enc-layer-12/att_weights/att_weights.hdf"),
    ],
    targets_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_standard-conformer/train_from_scratch/500-ep_bs-15000_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4_ce-aux-4-8/returnn_decoding/epoch-61-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/output/targets.hdf"),
    seg_starts_hdf=None,
    seg_lens_hdf=None,
    center_positions_hdf=None,
    target_blank_idx=None,
    ref_alignment_blank_idx=0,
    ref_alignment_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_hdf_align.hdf"),
    json_vocab_path=Path("/work/asr4/zeineldeen/setups-data/librispeech/2022-11-28--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.qhkNn2veTWkV/output/bpe.vocab"),
    ctc_alignment_hdf=None,
    segment_whitelist=["train-other-960/40-222-0033/40-222-0033"],
    ref_alignment_json_vocab_path=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_vocab"),
    plot_w_cog=False,
    titles=["Reversed encoder", "Standard encoder"],
    # titles=[f"Epoch {epoch * 4 // 20 if (epoch * 4 / 20).is_integer() else epoch * 4 / 20}" for epoch in epochs],
  )
  plot_att_weights_job.add_alias(f"flipped_vs_normal_cross_att_weights")
  tk.register_output(plot_att_weights_job.get_one_alias(), plot_att_weights_job.out_plot_dir)


def plot_gradients_wrt_different_layers():
  plot_att_weights_job = PlotAttentionWeightsJobV2(
    att_weight_hdf=[
      # Path(
      #   f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/x_linear/log-prob-grads_wrt_x_linear_log-space/att_weights.hdf"),
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/enc-8/log-prob-grads_wrt_enc-8_log-space/att_weights.hdf"),
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/enc-9/log-prob-grads_wrt_enc-9_log-space/att_weights.hdf"),
    ],
    targets_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_standard-conformer/train_from_scratch/500-ep_bs-15000_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4_ce-aux-4-8/returnn_decoding/epoch-61-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/output/targets.hdf"),
    seg_starts_hdf=None,
    seg_lens_hdf=None,
    center_positions_hdf=None,
    target_blank_idx=None,
    ref_alignment_blank_idx=0,
    ref_alignment_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_hdf_align.hdf"),
    json_vocab_path=Path("/work/asr4/zeineldeen/setups-data/librispeech/2022-11-28--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.qhkNn2veTWkV/output/bpe.vocab"),
    ctc_alignment_hdf=None,
    segment_whitelist=["train-other-960/40-222-0033/40-222-0033"],
    ref_alignment_json_vocab_path=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_vocab"),
    plot_w_cog=False,
    titles=["$G_9$", "$G_{10}$"],
    # titles=[f"Epoch {epoch * 4 // 20 if (epoch * 4 / 20).is_integer() else epoch * 4 / 20}" for epoch in epochs],
  )
  plot_att_weights_job.add_alias(f"gradients_wrt_different_layers/9_10")
  tk.register_output(plot_att_weights_job.get_one_alias(), plot_att_weights_job.out_plot_dir)

  plot_att_weights_job = PlotAttentionWeightsJobV2(
    att_weight_hdf=[
      # Path(
      #   f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/x_linear/log-prob-grads_wrt_x_linear_log-space/att_weights.hdf"),
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-10-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/enc-0/log-prob-grads_wrt_enc-0_log-space/att_weights.hdf"),
    ],
    targets_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_standard-conformer/train_from_scratch/500-ep_bs-15000_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4_ce-aux-4-8/returnn_decoding/epoch-61-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/output/targets.hdf"),
    seg_starts_hdf=None,
    seg_lens_hdf=None,
    center_positions_hdf=None,
    target_blank_idx=None,
    ref_alignment_blank_idx=0,
    ref_alignment_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_hdf_align.hdf"),
    json_vocab_path=Path("/work/asr4/zeineldeen/setups-data/librispeech/2022-11-28--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.qhkNn2veTWkV/output/bpe.vocab"),
    ctc_alignment_hdf=None,
    segment_whitelist=["train-other-960/40-222-0033/40-222-0033"],
    ref_alignment_json_vocab_path=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_vocab"),
    plot_w_cog=False,
    titles=["$G_1$"],
    # titles=[f"Epoch {epoch * 4 // 20 if (epoch * 4 / 20).is_integer() else epoch * 4 / 20}" for epoch in epochs],
  )
  plot_att_weights_job.add_alias(f"gradients_wrt_different_layers/1")
  tk.register_output(plot_att_weights_job.get_one_alias(), plot_att_weights_job.out_plot_dir)

  plot_att_weights_job = PlotAttentionWeightsJobV2(
    att_weight_hdf=[
      # Path(
      #   f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-60-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/x_linear/log-prob-grads_wrt_x_linear_log-space/att_weights.hdf"),
      Path(
        f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-10-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/work/x_linear/log-prob-grads_wrt_x_linear_log-space/att_weights.hdf"),
    ],
    targets_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_standard-conformer/train_from_scratch/500-ep_bs-15000_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4_ce-aux-4-8/returnn_decoding/epoch-61-checkpoint/no-lm/beam-size-12/train/analysis/analyze_gradients_ground-truth/40-222-0033/output/targets.hdf"),
    seg_starts_hdf=None,
    seg_lens_hdf=None,
    center_positions_hdf=None,
    target_blank_idx=None,
    ref_alignment_blank_idx=0,
    ref_alignment_hdf=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_hdf_align.hdf"),
    json_vocab_path=Path("/work/asr4/zeineldeen/setups-data/librispeech/2022-11-28--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.qhkNn2veTWkV/output/bpe.vocab"),
    ctc_alignment_hdf=None,
    segment_whitelist=["train-other-960/40-222-0033/40-222-0033"],
    ref_alignment_json_vocab_path=Path("/u/schmitt/experiments/03-09-24_aed_flipped_encoder/work/i6_experiments/users/schmitt/alignment/alignment/GmmAlignmentToWordBoundariesJob.Me7asSFVFnO6/output/out_vocab"),
    plot_w_cog=False,
    titles=["$G_0$"],
    # titles=[f"Epoch {epoch * 4 // 20 if (epoch * 4 / 20).is_integer() else epoch * 4 / 20}" for epoch in epochs],
  )
  plot_att_weights_job.add_alias(f"gradients_wrt_different_layers/0")
  tk.register_output(plot_att_weights_job.get_one_alias(), plot_att_weights_job.out_plot_dir)


def plot_flipped_self_att_weight_evolution():
  epochs = [10, 20, 30, 32, 34, 38, 40, 50]
  for head in range(8, 9):
    plot_self_att_weights_job = PlotSelfAttentionWeightsOverEpochsJob(
      att_weight_hdfs=[
        Path(
          f"/u/schmitt/experiments/03-09-24_aed_flipped_encoder/alias/models/ls_conformer/global_att/baseline_v1/baseline_rf/bpe1056/w-weight-feedback/w-att-ctx-in-state/nb-lstm/12-layer_512-dim_conformer-w-abs-pos/train_from_scratch/500-ep_bs-15000_mgpu-4_w-sp_curric_lr-dyn_lr_piecewise_linear_epoch-wise_v2_reg-v1_filter-data-312000.0_accum-4/returnn_decoding/epoch-{epoch}-checkpoint/no-lm/beam-size-12/train/analysis/dump_self_att/ground-truth/output/self-att-energies_head-{head}.hdf") for epoch in epochs
      ],
      epochs=epochs,
    )
    plot_self_att_weights_job.add_alias(f"flipped_self_att_evolution_head-{head}")
    tk.register_output(plot_self_att_weights_job.get_one_alias(), plot_self_att_weights_job.out_plot_dir)
