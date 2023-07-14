import torch


def export(*, model: torch.nn.Module, model_filename: str):
    dummy_data = torch.randn(1, 30, 50, device="cpu")
    dummy_data_len = torch.tensor([30], dtype=torch.int32)
    traced_model = torch.jit.trace(model.eval(), example_inputs=(dummy_data, dummy_data_len))
    torch.onnx.export(
        model=traced_model,
        args=(dummy_data, dummy_data_len),
        f=model_filename,
        verbose=True,
        input_names=["data", "data_len"],
        output_names=["classes", "sequence_mask"],
        opset_version=17,
        dynamic_axes={
            # dict value: manually named axes
            "data": {0: "batch", 1: "time"},
            "data_len": {0: "batch"},
            "targets": {0: "batch", 1: "time"},
        },
    )
