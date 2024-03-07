extern_data = {
    "audio_features": {"available_for_inference": True, "shape": (None, 1), "dim": 1},
    "bpe_labels": {
        "available_for_inference": False,
        "shape": (None,),
        "dim": 10025,
        "sparse": True,
    },
}


network = {
    "output": {
        "class": "subnetwork",
        "from": "data",
        "name_scope": "output/rec",  # make it like a RecLayer
        "subnetwork": {
            "target_embed_raw": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "n_out": 128,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "param_device": "CPU",
                "from": "data",
            },
            "target_embed_with_pos": {
                "class": "positional_encoding",
                "from": "target_embed_raw",
                "add_to_input": True,
            },
            "target_embed": {
                "class": "dropout",
                "from": "target_embed_with_pos",
                "dropout": 0.0,
            },
            "target_embed_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "target_embed",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_0_self_att_laynorm": {
                "class": "layer_norm",
                "from": "target_embed_lin",
            },
            "dec_0_self_att_att": {
                "class": "self_attention",
                "from": "dec_0_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_0_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_0_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_0_self_att_drop": {
                "class": "dropout",
                "from": "dec_0_self_att_lin",
                "dropout": 0.0,
            },
            "dec_0_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_0_self_att_drop", "target_embed_lin"],
                "n_out": 1024,
            },
            "dec_0_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_0_self_att_out",
            },
            "dec_0_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_0_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_0_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_0_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_0_ff_drop": {
                "class": "dropout",
                "from": "dec_0_ff_conv2",
                "dropout": 0.0,
            },
            "dec_0_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_0_ff_drop", "dec_0_self_att_out"],
                "n_out": 1024,
            },
            "dec_0": {"class": "copy", "from": "dec_0_ff_out"},
            "dec_1_self_att_laynorm": {"class": "layer_norm", "from": "dec_0"},
            "dec_1_self_att_att": {
                "class": "self_attention",
                "from": "dec_1_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_1_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_1_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_1_self_att_drop": {
                "class": "dropout",
                "from": "dec_1_self_att_lin",
                "dropout": 0.0,
            },
            "dec_1_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_1_self_att_drop", "dec_0"],
                "n_out": 1024,
            },
            "dec_1_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_1_self_att_out",
            },
            "dec_1_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_1_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_1_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_1_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_1_ff_drop": {
                "class": "dropout",
                "from": "dec_1_ff_conv2",
                "dropout": 0.0,
            },
            "dec_1_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_1_ff_drop", "dec_1_self_att_out"],
                "n_out": 1024,
            },
            "dec_1": {"class": "copy", "from": "dec_1_ff_out"},
            "dec_2_self_att_laynorm": {"class": "layer_norm", "from": "dec_1"},
            "dec_2_self_att_att": {
                "class": "self_attention",
                "from": "dec_2_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_2_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_2_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_2_self_att_drop": {
                "class": "dropout",
                "from": "dec_2_self_att_lin",
                "dropout": 0.0,
            },
            "dec_2_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_2_self_att_drop", "dec_1"],
                "n_out": 1024,
            },
            "dec_2_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_2_self_att_out",
            },
            "dec_2_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_2_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_2_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_2_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_2_ff_drop": {
                "class": "dropout",
                "from": "dec_2_ff_conv2",
                "dropout": 0.0,
            },
            "dec_2_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_2_ff_drop", "dec_2_self_att_out"],
                "n_out": 1024,
            },
            "dec_2": {"class": "copy", "from": "dec_2_ff_out"},
            "dec_3_self_att_laynorm": {"class": "layer_norm", "from": "dec_2"},
            "dec_3_self_att_att": {
                "class": "self_attention",
                "from": "dec_3_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_3_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_3_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_3_self_att_drop": {
                "class": "dropout",
                "from": "dec_3_self_att_lin",
                "dropout": 0.0,
            },
            "dec_3_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_3_self_att_drop", "dec_2"],
                "n_out": 1024,
            },
            "dec_3_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_3_self_att_out",
            },
            "dec_3_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_3_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_3_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_3_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_3_ff_drop": {
                "class": "dropout",
                "from": "dec_3_ff_conv2",
                "dropout": 0.0,
            },
            "dec_3_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_3_ff_drop", "dec_3_self_att_out"],
                "n_out": 1024,
            },
            "dec_3": {"class": "copy", "from": "dec_3_ff_out"},
            "dec_4_self_att_laynorm": {"class": "layer_norm", "from": "dec_3"},
            "dec_4_self_att_att": {
                "class": "self_attention",
                "from": "dec_4_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_4_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_4_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_4_self_att_drop": {
                "class": "dropout",
                "from": "dec_4_self_att_lin",
                "dropout": 0.0,
            },
            "dec_4_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_4_self_att_drop", "dec_3"],
                "n_out": 1024,
            },
            "dec_4_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_4_self_att_out",
            },
            "dec_4_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_4_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_4_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_4_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_4_ff_drop": {
                "class": "dropout",
                "from": "dec_4_ff_conv2",
                "dropout": 0.0,
            },
            "dec_4_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_4_ff_drop", "dec_4_self_att_out"],
                "n_out": 1024,
            },
            "dec_4": {"class": "copy", "from": "dec_4_ff_out"},
            "dec_5_self_att_laynorm": {"class": "layer_norm", "from": "dec_4"},
            "dec_5_self_att_att": {
                "class": "self_attention",
                "from": "dec_5_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_5_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_5_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_5_self_att_drop": {
                "class": "dropout",
                "from": "dec_5_self_att_lin",
                "dropout": 0.0,
            },
            "dec_5_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_5_self_att_drop", "dec_4"],
                "n_out": 1024,
            },
            "dec_5_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_5_self_att_out",
            },
            "dec_5_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_5_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_5_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_5_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_5_ff_drop": {
                "class": "dropout",
                "from": "dec_5_ff_conv2",
                "dropout": 0.0,
            },
            "dec_5_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_5_ff_drop", "dec_5_self_att_out"],
                "n_out": 1024,
            },
            "dec_5": {"class": "copy", "from": "dec_5_ff_out"},
            "dec_6_self_att_laynorm": {"class": "layer_norm", "from": "dec_5"},
            "dec_6_self_att_att": {
                "class": "self_attention",
                "from": "dec_6_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_6_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_6_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_6_self_att_drop": {
                "class": "dropout",
                "from": "dec_6_self_att_lin",
                "dropout": 0.0,
            },
            "dec_6_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_6_self_att_drop", "dec_5"],
                "n_out": 1024,
            },
            "dec_6_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_6_self_att_out",
            },
            "dec_6_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_6_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_6_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_6_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_6_ff_drop": {
                "class": "dropout",
                "from": "dec_6_ff_conv2",
                "dropout": 0.0,
            },
            "dec_6_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_6_ff_drop", "dec_6_self_att_out"],
                "n_out": 1024,
            },
            "dec_6": {"class": "copy", "from": "dec_6_ff_out"},
            "dec_7_self_att_laynorm": {"class": "layer_norm", "from": "dec_6"},
            "dec_7_self_att_att": {
                "class": "self_attention",
                "from": "dec_7_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_7_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_7_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_7_self_att_drop": {
                "class": "dropout",
                "from": "dec_7_self_att_lin",
                "dropout": 0.0,
            },
            "dec_7_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_7_self_att_drop", "dec_6"],
                "n_out": 1024,
            },
            "dec_7_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_7_self_att_out",
            },
            "dec_7_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_7_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_7_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_7_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_7_ff_drop": {
                "class": "dropout",
                "from": "dec_7_ff_conv2",
                "dropout": 0.0,
            },
            "dec_7_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_7_ff_drop", "dec_7_self_att_out"],
                "n_out": 1024,
            },
            "dec_7": {"class": "copy", "from": "dec_7_ff_out"},
            "dec_8_self_att_laynorm": {"class": "layer_norm", "from": "dec_7"},
            "dec_8_self_att_att": {
                "class": "self_attention",
                "from": "dec_8_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_8_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_8_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_8_self_att_drop": {
                "class": "dropout",
                "from": "dec_8_self_att_lin",
                "dropout": 0.0,
            },
            "dec_8_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_8_self_att_drop", "dec_7"],
                "n_out": 1024,
            },
            "dec_8_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_8_self_att_out",
            },
            "dec_8_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_8_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_8_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_8_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_8_ff_drop": {
                "class": "dropout",
                "from": "dec_8_ff_conv2",
                "dropout": 0.0,
            },
            "dec_8_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_8_ff_drop", "dec_8_self_att_out"],
                "n_out": 1024,
            },
            "dec_8": {"class": "copy", "from": "dec_8_ff_out"},
            "dec_9_self_att_laynorm": {"class": "layer_norm", "from": "dec_8"},
            "dec_9_self_att_att": {
                "class": "self_attention",
                "from": "dec_9_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_9_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_9_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_9_self_att_drop": {
                "class": "dropout",
                "from": "dec_9_self_att_lin",
                "dropout": 0.0,
            },
            "dec_9_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_9_self_att_drop", "dec_8"],
                "n_out": 1024,
            },
            "dec_9_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_9_self_att_out",
            },
            "dec_9_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_9_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_9_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_9_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_9_ff_drop": {
                "class": "dropout",
                "from": "dec_9_ff_conv2",
                "dropout": 0.0,
            },
            "dec_9_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_9_ff_drop", "dec_9_self_att_out"],
                "n_out": 1024,
            },
            "dec_9": {"class": "copy", "from": "dec_9_ff_out"},
            "dec_10_self_att_laynorm": {"class": "layer_norm", "from": "dec_9"},
            "dec_10_self_att_att": {
                "class": "self_attention",
                "from": "dec_10_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_10_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_10_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_10_self_att_drop": {
                "class": "dropout",
                "from": "dec_10_self_att_lin",
                "dropout": 0.0,
            },
            "dec_10_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_10_self_att_drop", "dec_9"],
                "n_out": 1024,
            },
            "dec_10_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_10_self_att_out",
            },
            "dec_10_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_10_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_10_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_10_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_10_ff_drop": {
                "class": "dropout",
                "from": "dec_10_ff_conv2",
                "dropout": 0.0,
            },
            "dec_10_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_10_ff_drop", "dec_10_self_att_out"],
                "n_out": 1024,
            },
            "dec_10": {"class": "copy", "from": "dec_10_ff_out"},
            "dec_11_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_10",
            },
            "dec_11_self_att_att": {
                "class": "self_attention",
                "from": "dec_11_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_11_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_11_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_11_self_att_drop": {
                "class": "dropout",
                "from": "dec_11_self_att_lin",
                "dropout": 0.0,
            },
            "dec_11_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_11_self_att_drop", "dec_10"],
                "n_out": 1024,
            },
            "dec_11_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_11_self_att_out",
            },
            "dec_11_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_11_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_11_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_11_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_11_ff_drop": {
                "class": "dropout",
                "from": "dec_11_ff_conv2",
                "dropout": 0.0,
            },
            "dec_11_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_11_ff_drop", "dec_11_self_att_out"],
                "n_out": 1024,
            },
            "dec_11": {"class": "copy", "from": "dec_11_ff_out"},
            "dec_12_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_11",
            },
            "dec_12_self_att_att": {
                "class": "self_attention",
                "from": "dec_12_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_12_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_12_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_12_self_att_drop": {
                "class": "dropout",
                "from": "dec_12_self_att_lin",
                "dropout": 0.0,
            },
            "dec_12_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_12_self_att_drop", "dec_11"],
                "n_out": 1024,
            },
            "dec_12_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_12_self_att_out",
            },
            "dec_12_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_12_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_12_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_12_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_12_ff_drop": {
                "class": "dropout",
                "from": "dec_12_ff_conv2",
                "dropout": 0.0,
            },
            "dec_12_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_12_ff_drop", "dec_12_self_att_out"],
                "n_out": 1024,
            },
            "dec_12": {"class": "copy", "from": "dec_12_ff_out"},
            "dec_13_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_12",
            },
            "dec_13_self_att_att": {
                "class": "self_attention",
                "from": "dec_13_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_13_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_13_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_13_self_att_drop": {
                "class": "dropout",
                "from": "dec_13_self_att_lin",
                "dropout": 0.0,
            },
            "dec_13_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_13_self_att_drop", "dec_12"],
                "n_out": 1024,
            },
            "dec_13_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_13_self_att_out",
            },
            "dec_13_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_13_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_13_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_13_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_13_ff_drop": {
                "class": "dropout",
                "from": "dec_13_ff_conv2",
                "dropout": 0.0,
            },
            "dec_13_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_13_ff_drop", "dec_13_self_att_out"],
                "n_out": 1024,
            },
            "dec_13": {"class": "copy", "from": "dec_13_ff_out"},
            "dec_14_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_13",
            },
            "dec_14_self_att_att": {
                "class": "self_attention",
                "from": "dec_14_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_14_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_14_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_14_self_att_drop": {
                "class": "dropout",
                "from": "dec_14_self_att_lin",
                "dropout": 0.0,
            },
            "dec_14_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_14_self_att_drop", "dec_13"],
                "n_out": 1024,
            },
            "dec_14_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_14_self_att_out",
            },
            "dec_14_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_14_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_14_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_14_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_14_ff_drop": {
                "class": "dropout",
                "from": "dec_14_ff_conv2",
                "dropout": 0.0,
            },
            "dec_14_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_14_ff_drop", "dec_14_self_att_out"],
                "n_out": 1024,
            },
            "dec_14": {"class": "copy", "from": "dec_14_ff_out"},
            "dec_15_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_14",
            },
            "dec_15_self_att_att": {
                "class": "self_attention",
                "from": "dec_15_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_15_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_15_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_15_self_att_drop": {
                "class": "dropout",
                "from": "dec_15_self_att_lin",
                "dropout": 0.0,
            },
            "dec_15_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_15_self_att_drop", "dec_14"],
                "n_out": 1024,
            },
            "dec_15_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_15_self_att_out",
            },
            "dec_15_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_15_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_15_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_15_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_15_ff_drop": {
                "class": "dropout",
                "from": "dec_15_ff_conv2",
                "dropout": 0.0,
            },
            "dec_15_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_15_ff_drop", "dec_15_self_att_out"],
                "n_out": 1024,
            },
            "dec_15": {"class": "copy", "from": "dec_15_ff_out"},
            "dec_16_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_15",
            },
            "dec_16_self_att_att": {
                "class": "self_attention",
                "from": "dec_16_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_16_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_16_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_16_self_att_drop": {
                "class": "dropout",
                "from": "dec_16_self_att_lin",
                "dropout": 0.0,
            },
            "dec_16_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_16_self_att_drop", "dec_15"],
                "n_out": 1024,
            },
            "dec_16_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_16_self_att_out",
            },
            "dec_16_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_16_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_16_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_16_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_16_ff_drop": {
                "class": "dropout",
                "from": "dec_16_ff_conv2",
                "dropout": 0.0,
            },
            "dec_16_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_16_ff_drop", "dec_16_self_att_out"],
                "n_out": 1024,
            },
            "dec_16": {"class": "copy", "from": "dec_16_ff_out"},
            "dec_17_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_16",
            },
            "dec_17_self_att_att": {
                "class": "self_attention",
                "from": "dec_17_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_17_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_17_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_17_self_att_drop": {
                "class": "dropout",
                "from": "dec_17_self_att_lin",
                "dropout": 0.0,
            },
            "dec_17_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_17_self_att_drop", "dec_16"],
                "n_out": 1024,
            },
            "dec_17_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_17_self_att_out",
            },
            "dec_17_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_17_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_17_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_17_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_17_ff_drop": {
                "class": "dropout",
                "from": "dec_17_ff_conv2",
                "dropout": 0.0,
            },
            "dec_17_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_17_ff_drop", "dec_17_self_att_out"],
                "n_out": 1024,
            },
            "dec_17": {"class": "copy", "from": "dec_17_ff_out"},
            "dec_18_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_17",
            },
            "dec_18_self_att_att": {
                "class": "self_attention",
                "from": "dec_18_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_18_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_18_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_18_self_att_drop": {
                "class": "dropout",
                "from": "dec_18_self_att_lin",
                "dropout": 0.0,
            },
            "dec_18_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_18_self_att_drop", "dec_17"],
                "n_out": 1024,
            },
            "dec_18_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_18_self_att_out",
            },
            "dec_18_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_18_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_18_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_18_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_18_ff_drop": {
                "class": "dropout",
                "from": "dec_18_ff_conv2",
                "dropout": 0.0,
            },
            "dec_18_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_18_ff_drop", "dec_18_self_att_out"],
                "n_out": 1024,
            },
            "dec_18": {"class": "copy", "from": "dec_18_ff_out"},
            "dec_19_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_18",
            },
            "dec_19_self_att_att": {
                "class": "self_attention",
                "from": "dec_19_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_19_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_19_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_19_self_att_drop": {
                "class": "dropout",
                "from": "dec_19_self_att_lin",
                "dropout": 0.0,
            },
            "dec_19_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_19_self_att_drop", "dec_18"],
                "n_out": 1024,
            },
            "dec_19_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_19_self_att_out",
            },
            "dec_19_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_19_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_19_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_19_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_19_ff_drop": {
                "class": "dropout",
                "from": "dec_19_ff_conv2",
                "dropout": 0.0,
            },
            "dec_19_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_19_ff_drop", "dec_19_self_att_out"],
                "n_out": 1024,
            },
            "dec_19": {"class": "copy", "from": "dec_19_ff_out"},
            "dec_20_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_19",
            },
            "dec_20_self_att_att": {
                "class": "self_attention",
                "from": "dec_20_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_20_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_20_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_20_self_att_drop": {
                "class": "dropout",
                "from": "dec_20_self_att_lin",
                "dropout": 0.0,
            },
            "dec_20_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_20_self_att_drop", "dec_19"],
                "n_out": 1024,
            },
            "dec_20_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_20_self_att_out",
            },
            "dec_20_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_20_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_20_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_20_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_20_ff_drop": {
                "class": "dropout",
                "from": "dec_20_ff_conv2",
                "dropout": 0.0,
            },
            "dec_20_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_20_ff_drop", "dec_20_self_att_out"],
                "n_out": 1024,
            },
            "dec_20": {"class": "copy", "from": "dec_20_ff_out"},
            "dec_21_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_20",
            },
            "dec_21_self_att_att": {
                "class": "self_attention",
                "from": "dec_21_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_21_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_21_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_21_self_att_drop": {
                "class": "dropout",
                "from": "dec_21_self_att_lin",
                "dropout": 0.0,
            },
            "dec_21_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_21_self_att_drop", "dec_20"],
                "n_out": 1024,
            },
            "dec_21_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_21_self_att_out",
            },
            "dec_21_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_21_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_21_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_21_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_21_ff_drop": {
                "class": "dropout",
                "from": "dec_21_ff_conv2",
                "dropout": 0.0,
            },
            "dec_21_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_21_ff_drop", "dec_21_self_att_out"],
                "n_out": 1024,
            },
            "dec_21": {"class": "copy", "from": "dec_21_ff_out"},
            "dec_22_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_21",
            },
            "dec_22_self_att_att": {
                "class": "self_attention",
                "from": "dec_22_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_22_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_22_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_22_self_att_drop": {
                "class": "dropout",
                "from": "dec_22_self_att_lin",
                "dropout": 0.0,
            },
            "dec_22_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_22_self_att_drop", "dec_21"],
                "n_out": 1024,
            },
            "dec_22_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_22_self_att_out",
            },
            "dec_22_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_22_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_22_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_22_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_22_ff_drop": {
                "class": "dropout",
                "from": "dec_22_ff_conv2",
                "dropout": 0.0,
            },
            "dec_22_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_22_ff_drop", "dec_22_self_att_out"],
                "n_out": 1024,
            },
            "dec_22": {"class": "copy", "from": "dec_22_ff_out"},
            "dec_23_self_att_laynorm": {
                "class": "layer_norm",
                "from": "dec_22",
            },
            "dec_23_self_att_att": {
                "class": "self_attention",
                "from": "dec_23_self_att_laynorm",
                "n_out": 1024,
                "num_heads": 8,
                "total_key_dim": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
                "attention_left_only": True,
            },
            "dec_23_self_att_lin": {
                "class": "linear",
                "activation": None,
                "with_bias": False,
                "from": "dec_23_self_att_att",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_23_self_att_drop": {
                "class": "dropout",
                "from": "dec_23_self_att_lin",
                "dropout": 0.0,
            },
            "dec_23_self_att_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_23_self_att_drop", "dec_22"],
                "n_out": 1024,
            },
            "dec_23_ff_laynorm": {
                "class": "layer_norm",
                "from": "dec_23_self_att_out",
            },
            "dec_23_ff_conv1": {
                "class": "linear",
                "activation": "relu",
                "with_bias": True,
                "from": "dec_23_ff_laynorm",
                "n_out": 4096,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_23_ff_conv2": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "dec_23_ff_conv1",
                "n_out": 1024,
                "forward_weights_init": "variance_scaling_initializer(mode='fan_in', "
                "distribution='uniform', scale=1.0)",
            },
            "dec_23_ff_drop": {
                "class": "dropout",
                "from": "dec_23_ff_conv2",
                "dropout": 0.0,
            },
            "dec_23_ff_out": {
                "class": "combine",
                "kind": "add",
                "from": ["dec_23_ff_drop", "dec_23_self_att_out"],
                "n_out": 1024,
            },
            "dec_23": {"class": "copy", "from": "dec_23_ff_out"},
            "decoder": {"class": "layer_norm", "from": "dec_23"},
            "output": {
                "class": "linear",
                "activation": None,
                "with_bias": True,
                "from": "decoder",
                "n_out": 10025,
            },
        },
        # "load_on_init": {
        #     "filename": "/work/asr3/irie/experiments/lm/librispeech/2018-03-05--lmbpe-zeyer/data-train/transfo_24_d00.4096_1024.sgd.lr1.8_heads/bk-net-model/network.023",
        #     "params_prefix": "",
        #     "load_if_prefix": "lm_output/",
        # },
    }
    # "lm_output_prob": {
    #     "class": "activation",
    #     "activation": "softmax",
    #     "from": "lm_output",
    #     "target": "bpe_labels",
    # },
    # "combo_output_prob": {
    #     "class": "eval",
    #     "eval": "safe_log(source(0)) + 0.56 * safe_log(source(1)) - 0.4 * safe_log(source(2))",
    #     "from": ["output_prob", "lm_output_prob", "prior_output_prob"],
    # },
}

preload_from_files = {
    "prior_lm": {
        "filename": "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/returnn/training/AverageTFCheckpointsJob.BxqgICRSGkgb/output/model/average",
        "prefix": "prior_",
    },
    "mini_lstm": {
        "filename": "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/returnn/training/GetBestTFCheckpointJob.dWby3NtOKdLo/output/model/checkpoint",
        "prefix": "mini_",
    },
}

search_data = {
    "class": "MetaDataset",
    "data_map": {
        "audio_features": ("zip_dataset", "data"),
        "bpe_labels": ("zip_dataset", "classes"),
    },
    "datasets": {
        "zip_dataset": {
            "class": "OggZipDataset",
            "path": "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/returnn/oggzip/BlissToOggZipJob.NSdIHfk1iw2M/output/out.ogg.zip",
            "use_cache_manager": True,
            "audio": {
                "features": "raw",
                "peak_normalization": True,
                "preemphasis": None,
            },
            "targets": {
                "class": "BytePairEncoding",
                "bpe_file": "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.vTq56NZ8STWt/output/bpe.codes",
                "vocab_file": "/u/zeineldeen/setups/ubuntu_22_setups/2023-04-17--conformer-att/work/i6_core/text/label/subword_nmt/train/ReturnnTrainBpeJob.vTq56NZ8STWt/output/bpe.vocab",
                "unknown_label": "<unk>",
                "seq_postfix": [0],
            },
            "segment_file": None,
            "partition_epoch": 1,
            "seq_ordering": "sorted_reverse",
        }
    },
    "seq_order_control_dataset": "zip_dataset",
}
