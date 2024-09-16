import os

from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att.baseline_v1 import (
  baseline
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.global_att import (
  train, recog
)
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23_rf.pipelines.pipeline_ls_conf.checkpoints import external_checkpoints, default_import_model_name
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23.dependencies.labels.v2.librispeech.phonemes.gmm_alignments import LIBRISPEECH_GMM_ALIGNMENT_CONVERTED
from i6_experiments.users.schmitt.experiments.config.pipelines.global_vs_segmental_2022_23.dependencies.labels.v2.librispeech.phonemes.gmm_alignments import LIBRISPEECH_GMM_WORD_ALIGNMENT


def run_exps():
  for model_alias, config_builder in baseline.global_att_baseline_rf(
          use_weight_feedback=True,
          label_type="bpe1056",
  ):
    for train_alias, checkpoint in (
            (f"{model_alias}/import_glob.conformer.luca.bpe1k.w-ctc", external_checkpoints["luca-aed-bpe1k-w-ctc"]),
            (f"{model_alias}/import_glob.conformer.luca.bpe1k.wo-ctc", external_checkpoints["luca-aed-bpe1k-wo-ctc"]),
    ):
      recog.global_att_returnn_label_sync_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=("best-luca",),
        run_analysis=True,
        analyze_gradients=True,
        plot_att_weights=False,
      )

    # v1: training, where i observed the flipped encoder after about 60 sub-epochs
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
    ):
      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch % 20 == 0 or epoch in (5, 10, 20, 30) or epoch in range(1, 60, 5):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
          )

    # v2: same as v1, but use epoch-wise OCLR
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
      keep_epochs=list(range(1, 240)) + [500],
      lr_scheduling_type="dyn_lr_piecewise_linear_epoch-wise_v2",
    ):
      recog.global_att_returnn_label_sync_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=("last",),
        corpus_keys=("dev-other", "dev-clean", "test-other", "test-clean"),
      )
      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch in [22, 55, 60] or epoch in range(1, 60, 5):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
            only_do_analysis=True,
          )

        if epoch == 406:
          for input_layer_name in ["encoder_input", "frontend_input"]:
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

      # all_epochs = range(500, 0, -1)
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

    # v3: same as v2, but filter out data > 19.5s
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
      keep_epochs=list(range(1, 240)) + [500],
      lr_scheduling_type="dyn_lr_piecewise_linear_epoch-wise_v2",
      filter_data_len=19.5 * 16_000,  # sample rate 16kHz
    ):
      recog.global_att_returnn_label_sync_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=("last",),
        corpus_keys=("dev-other", "dev-clean", "test-other", "test-clean"),
      )

      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch in [31, 55, 60] or epoch in range(32, 55) or epoch in range(1, 60, 5):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
            only_do_analysis=True,
          )

      # all_epochs = range(500, 0, -1)
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

    # v4: same as v2, but filter out targets > 75
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
      keep_epochs=list(range(1, 240)) + [500],
      lr_scheduling_type="dyn_lr_piecewise_linear_epoch-wise_v2",
      filter_target_len=75,  # sample rate 16kHz
    ):
      recog.global_att_returnn_label_sync_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=("last",),
        corpus_keys=("dev-other", "dev-clean", "test-other", "test-clean"),
      )

      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch in [60, 80, 116] or epoch in range(1, 60, 5) or epoch in range(50, 70):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
            only_do_analysis=True,
          )

      # all_epochs = range(500, 0, -1)
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
  ) in [
    ["v3_big", None, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 24], # v3_big: same as v2, but on 24gb GPU with batch size 40k - not flipped
    ["v3_big_rand-1337", 1337, None, None, False, 12, 512, False, False, False, list(range(1, 240)), 24],  # v3_big_rand-1337 - flipped
    ["v3_big_rand-8264", 8264, None, None, False, 12, 512, False, False, False, [121, 131, 141], 24],  # v3_big_rand-8264 - flipped
    ["v3_big_rand-2160", 2160, None, None, False, 12, 512, False, False, False, [121, 131, 141], 24],  # v3_big_rand-2160 - flipped
    # ["v3_big_rand-9999", 9999, None, None, False, 12, 512, False, False, False, [121, 131, 141]],  # v3_big_rand-9999
    ["v5_big", None, 21, None, False, 12, 512, False, False, False, list(range(1, 240)), 24],  # v5_big: same as v3_big, but enable self attention only after 20 sub-epochs (1 full epoch) - not flipped
    # ["v6_big", None, None, None, False, 12, 512, False, False, True, list(range(1, 240)), 24],  # v6_big: same as v3_big, but use both absolute and relative positional encodings
    # ["v7_big", None, None, None, True, 12, 512, False, False, False, [121, 131, 141]],  # v7_big: same as v3_big, but do not use final layer norm in conformer encoder layers
    ["v8_big", None, None, (4, 8), False, 12, 512, False, False, False, list(range(1, 141, 10)), 24],  # v8_big: same as v3_big, but use CTC aux loss - not flipped
    # ["v9_big", None, None, None, False, 17, 400, False, False, False, list(range(1, 240)), 24],  # v9_big: same as v3_big, but use 17 instead of 12 encoder layers and 400 instead of 512 output dim
    # ["v9", None, None, None, False, 17, 400, False, False, False, list(range(1, 240)), 11], # v9: same as v3_big, but use 17 instead of 12 encoder layers and 400 instead of 512 output dim
    # ["v10_big", None, None, None, False, 12, 512, True, False, False, list(range(1, 240)), 24],  # v10_big: same as v3_big, but without convolution module in conformer encoder layers
    # ["v11_big", None, None, None, False, 12, 512, False, True, False, [121, 131, 141]],  # v11_big: same as v3_big, but without pos encoding
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
    ):
      if gpu_mem_rqmt == 24:
        use_mgpu = False
        accum_grad_multiple_step = 2
      else:
        use_mgpu = True
        accum_grad_multiple_step = 4

      for train_alias, checkpoint in train.train_global_att(
              alias=model_alias,
              config_builder=config_builder,
              n_epochs=2_000,
              batch_size=30_000 if alias == "v9_big" else 35_000,
              keep_epochs=keep_epochs,
              lr_scheduling_type="dyn_lr_piecewise_linear_epoch-wise_v2",
              gpu_mem_rqmt=gpu_mem_rqmt,
              accum_grad_multiple_step=accum_grad_multiple_step,
              use_mgpu=use_mgpu,
              use_torch_amp=False,
              filter_data_len=19.5 * 16_000,
              random_seed=random_seed,
              disable_enc_self_att_until_epoch=disable_self_att_until_epoch,
              ce_aux_loss_layers=ctc_aux_loss_layers,
      ):
        recog.global_att_returnn_label_sync_beam_search(
          alias=train_alias,
          config_builder=config_builder,
          checkpoint=checkpoint,
        )

        analysis_epochs = [121, 131]
        if alias in ("v3_big",):
          analysis_epochs += [1355]
        if alias in ("v3_big", "v3_big_rand-1337", "v5_big", "v6_big"):
          analysis_epochs += list(range(1, 141, 10))
        if alias in ("v3_big", "v3_big_rand-1337"):
          analysis_epochs += list(range(90, 141))
        if alias in ("v3_big_rand-8264",):
          analysis_epochs += list(range(118, 131)) + list(range(10, 111, 10))

        for epoch, chckpt in checkpoint["checkpoints"].items():
          if alias == "v3_big_rand-1337" and epoch == 130:
            analysis_do_forced_align_on_gradients = True
          else:
            analysis_do_forced_align_on_gradients = False

          if epoch in analysis_epochs:
            recog.global_att_returnn_label_sync_beam_search(
              alias=train_alias,
              config_builder=config_builder,
              checkpoint=chckpt,
              checkpoint_aliases=(f"epoch-{epoch}",),
              run_analysis=True,
              analyze_gradients=True,
              only_do_analysis=True,
              analysis_do_forced_align_on_gradients=analysis_do_forced_align_on_gradients,
            )
          if alias == "v3_big" and epoch in range(51, 141, 10):
            recog.global_att_returnn_label_sync_beam_search(
              alias=train_alias,
              config_builder=config_builder,
              checkpoint=chckpt,
              checkpoint_aliases=(f"epoch-{epoch}",),
              run_analysis=True,
              analyze_gradients=True,
              only_do_analysis=True,
              analysis_plot_encoder_gradient_graph=True,
              att_weight_seq_tags=["dev-other/116-288047-0013/116-288047-0013"]
            )
          if (alias == "v8_big" and epoch == 919) or (
                  alias == "v3_big" and epoch == 1676) or (
                  alias == "v3_big" and epoch == 1743) or (
                  alias == "v3_big_rand-1337" and epoch == 646) or (
                  alias == "v3_big_rand-1337" and epoch == 141) or (
                  alias == "v3_big" and epoch == 141) or (
          ):
            if (alias == "v3_big" and epoch == 1743) or (
                    alias == "v3_big_rand-1337" and epoch == 646) or (
                    alias == "v3_big_rand-1337" and epoch == 141) or (
                    alias == "v3_big" and epoch == 141
            ):
              input_layer_names = ["frontend_input"]
            else:
              input_layer_names = ["encoder_input", "frontend_input"]
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

        # epochs = [91, 90, 81, 80, 71, 70, 61, 60]
        # all_epochs = range(2000, 0, -1)
        # for epochs_ in [epochs, all_epochs]:
        #   for epoch in epochs_:
        #     chckpt = checkpoint["checkpoints"][epoch]
        #
        #     if os.path.exists(chckpt.path):
        #       recog.global_att_returnn_label_sync_beam_search(
        #         alias=train_alias,
        #         config_builder=config_builder,
        #         checkpoint=chckpt,
        #         checkpoint_aliases=(f"epoch-{epoch}",),
        #         corpus_keys=("train",),
        #         run_analysis=True,
        #         analyze_gradients=True,
        #         only_do_analysis=True,
        #         att_weight_seq_tags=["train-other-960/1578-6379-0013/1578-6379-0013"],
        #         analysis_ref_alignment_opts={
        #           "ref_alignment_hdf": LIBRISPEECH_GMM_WORD_ALIGNMENT.alignment_paths["train"],
        #           "ref_alignment_blank_idx": LIBRISPEECH_GMM_WORD_ALIGNMENT.model_hyperparameters.blank_idx,
        #           "ref_alignment_vocab_path": LIBRISPEECH_GMM_WORD_ALIGNMENT.vocab_path,
        #         }
        #       )
        #       break  # only do this for the first existing checkpoint

  from i6_core.returnn.training import PtCheckpoint
  from sisyphus import Path
  for model_alias, config_builder in baseline.global_att_baseline_rf(
          use_weight_feedback=True,
          label_type="bpe1056",
          conformer_conv_w_zero_padding=True,
          conv_frontend_w_zero_padding=True,
  ):
    for train_alias, checkpoint in (
            (f"{model_alias}/import_1k-baseline-wo-ctc", PtCheckpoint(Path("/work/asr3/zeyer/schmitt/sisyphus_work_dirs/segmental_models_2022_23_rf/i6_core/returnn/training/ReturnnTrainingJob.eoGg1OAu9UaY/output/models/epoch.1743.pt"))),
    ):
      recog.global_att_returnn_label_sync_beam_search(
        alias=train_alias,
        config_builder=config_builder,
        checkpoint=checkpoint,
        checkpoint_aliases=(f"epoch-{1743}",),
        run_analysis=True,
        analysis_dump_gradients=True,
        only_do_analysis=True,
        corpus_keys=("train",),
        att_weight_seq_tags=None,
        analysis_dump_gradients_input_layer_name="frontend_input",
      )

  for model_alias, config_builder in baseline.global_att_baseline_rf(
          use_weight_feedback=True,
          decoder_state="nb-2linear-ctx1",
          label_type="bpe1056",
  ):
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
      use_mgpu=False,
    ):
      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch % 20 == 0 and epoch not in (160, 20, 40, 360, 400, 440, 240, 100):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
          )

  for model_alias, config_builder in baseline.global_att_baseline_rf(
          use_weight_feedback=False,
          decoder_state="nb-2linear-ctx1",
          label_type="bpe1056",
  ):
    for train_alias, checkpoint in train.train_global_att(
      alias=model_alias,
      config_builder=config_builder,
      n_epochs=500,
      use_mgpu=False,
    ):
      for epoch, chckpt in checkpoint["checkpoints"].items():
        if epoch % 20 == 0 and epoch not in (240, 360, 140, 160):
          recog.global_att_returnn_label_sync_beam_search(
            alias=train_alias,
            config_builder=config_builder,
            checkpoint=chckpt,
            checkpoint_aliases=(f"epoch-{epoch}",),
            run_analysis=True,
            analyze_gradients=True,
          )




