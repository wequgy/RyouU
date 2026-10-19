"""Convert official PyTorch MiniFASNetV2 weights to ONNX.

Dev-only script (requires torch, onnx, onnxruntime).
Downloads 2.7_80x80_MiniFASNetV2.pth from the official minivision-ai/Silent-Face-Anti-Spoofing repo,
builds the exact MiniFASNetV2 model architecture, exports to ONNX at 80x80 input resolution,
and verifies numerical equivalence between PyTorch and ONNX Runtime outputs within 1e-4 tolerance.
"""
import argparse
import hashlib
from collections import OrderedDict
from pathlib import Path
import urllib.request

import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn as nn

OFFICIAL_PTH_URL = (
    "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/"
    "master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
)
EXPECTED_ONNX_SHA256 = "d7b3cd9ba8a7ceb13baa8c4720902e27ca3112eff52f926c08804af6b6eecc7b"


class Flatten(nn.Module):
    def forward(self, input):
        return input.view(input.size(0), -1)


class Conv_block(nn.Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_c)
        self.prelu = nn.PReLU(out_c)

    def forward(self, x):
        return self.prelu(self.bn(self.conv(x)))


class Linear_block(nn.Module):
    def __init__(self, in_c, out_c, kernel=(1, 1), stride=(1, 1), padding=(0, 0), groups=1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_channels=out_c, kernel_size=kernel, groups=groups, stride=stride, padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_c)

    def forward(self, x):
        return self.bn(self.conv(x))


class Depth_Wise(nn.Module):
    def __init__(self, c1, c2, c3, residual=False, kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=1):
        super().__init__()
        self.conv = Conv_block(c1[0], out_c=c1[1], kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.conv_dw = Conv_block(c2[0], c2[1], groups=c2[0], kernel=kernel, padding=padding, stride=stride)
        self.project = Linear_block(c3[0], c3[1], kernel=(1, 1), padding=(0, 0), stride=(1, 1))
        self.residual = residual

    def forward(self, x):
        short_cut = x if self.residual else None
        x = self.project(self.conv_dw(self.conv(x)))
        return (short_cut + x) if self.residual else x


class Residual(nn.Module):
    def __init__(self, c1, c2, c3, num_block, groups, kernel=(3, 3), stride=(1, 1), padding=(1, 1)):
        super().__init__()
        modules = [
            Depth_Wise(c1[i], c2[i], c3[i], residual=True, kernel=kernel, padding=padding, stride=stride, groups=groups)
            for i in range(num_block)
        ]
        self.model = nn.Sequential(*modules)

    def forward(self, x):
        return self.model(x)


class MiniFASNet(nn.Module):
    def __init__(self, keep, embedding_size=128, conv6_kernel=(5, 5), drop_p=0.2, num_classes=3, img_channel=3):
        super().__init__()
        self.embedding_size = embedding_size
        self.conv1 = Conv_block(img_channel, keep[0], kernel=(3, 3), stride=(2, 2), padding=(1, 1))
        self.conv2_dw = Conv_block(keep[0], keep[1], kernel=(3, 3), stride=(1, 1), padding=(1, 1), groups=keep[1])

        self.conv_23 = Depth_Wise((keep[1], keep[2]), (keep[2], keep[3]), (keep[3], keep[4]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[3])

        c1 = [(keep[4], keep[5]), (keep[7], keep[8]), (keep[10], keep[11]), (keep[13], keep[14])]
        c2 = [(keep[5], keep[6]), (keep[8], keep[9]), (keep[11], keep[12]), (keep[14], keep[15])]
        c3 = [(keep[6], keep[7]), (keep[9], keep[10]), (keep[12], keep[13]), (keep[15], keep[16])]
        self.conv_3 = Residual(c1, c2, c3, num_block=4, groups=keep[4], kernel=(3, 3), stride=(1, 1), padding=(1, 1))

        self.conv_34 = Depth_Wise((keep[16], keep[17]), (keep[17], keep[18]), (keep[18], keep[19]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[19])

        c1 = [(keep[19], keep[20]), (keep[22], keep[23]), (keep[25], keep[26]), (keep[28], keep[29]), (keep[31], keep[32]), (keep[34], keep[35])]
        c2 = [(keep[20], keep[21]), (keep[23], keep[24]), (keep[26], keep[27]), (keep[29], keep[30]), (keep[32], keep[33]), (keep[35], keep[36])]
        c3 = [(keep[21], keep[22]), (keep[24], keep[25]), (keep[27], keep[28]), (keep[30], keep[31]), (keep[33], keep[34]), (keep[36], keep[37])]
        self.conv_4 = Residual(c1, c2, c3, num_block=6, groups=keep[19], kernel=(3, 3), stride=(1, 1), padding=(1, 1))

        self.conv_45 = Depth_Wise((keep[37], keep[38]), (keep[38], keep[39]), (keep[39], keep[40]), kernel=(3, 3), stride=(2, 2), padding=(1, 1), groups=keep[40])

        c1 = [(keep[40], keep[41]), (keep[43], keep[44])]
        c2 = [(keep[41], keep[42]), (keep[44], keep[45])]
        c3 = [(keep[42], keep[43]), (keep[45], keep[46])]
        self.conv_5 = Residual(c1, c2, c3, num_block=2, groups=keep[40], kernel=(3, 3), stride=(1, 1), padding=(1, 1))

        self.conv_6_sep = Conv_block(keep[46], keep[47], kernel=(1, 1), stride=(1, 1), padding=(0, 0))
        self.conv_6_dw = Linear_block(keep[47], keep[48], groups=keep[48], kernel=conv6_kernel, stride=(1, 1), padding=(0, 0))
        self.conv_6_flatten = Flatten()
        self.linear = nn.Linear(512, embedding_size, bias=False)
        self.bn = nn.BatchNorm1d(embedding_size)
        self.drop = nn.Dropout(p=drop_p)
        self.prob = nn.Linear(embedding_size, num_classes, bias=False)

    def forward(self, x):
        out = self.conv1(x)
        out = self.conv2_dw(out)
        out = self.conv_23(out)
        out = self.conv_3(out)
        out = self.conv_34(out)
        out = self.conv_4(out)
        out = self.conv_45(out)
        out = self.conv_5(out)
        out = self.conv_6_sep(out)
        out = self.conv_6_dw(out)
        out = self.conv_6_flatten(out)
        if self.embedding_size != 512:
            out = self.linear(out)
        out = self.bn(out)
        out = self.drop(out)
        out = self.prob(out)
        return out


def build_minifasnet_v2() -> MiniFASNet:
    keep_1_8M_ = [
        32, 32, 103, 103, 64, 13, 13, 64, 13, 13, 64, 13,
        13, 64, 13, 13, 64, 231, 231, 128, 231, 231, 128, 52,
        52, 128, 26, 26, 128, 77, 77, 128, 26, 26, 128, 26, 26,
        128, 308, 308, 128, 26, 26, 128, 26, 26, 128, 512, 512,
    ]
    return MiniFASNet(keep_1_8M_, embedding_size=128, conv6_kernel=(5, 5), drop_p=0.2, num_classes=3)


def download_official_weights(target_path: Path) -> Path:
    if target_path.exists():
        print(f"[OK] Official .pth already present: {target_path}")
        return target_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] Downloading official weights from {OFFICIAL_PTH_URL}...")
    req = urllib.request.Request(OFFICIAL_PTH_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(target_path, "wb") as f:
        f.write(resp.read())
    print(f"[OK] Downloaded weights to {target_path}")
    return target_path


def convert_and_verify(pth_path: Path, output_onnx_path: Path, num_test_samples: int = 5, tolerance: float = 1e-4) -> str:
    print(f"Loading PyTorch weights from {pth_path}...")
    model = build_minifasnet_v2()
    raw_sd = torch.load(str(pth_path), map_location="cpu")
    clean_sd = OrderedDict((k.replace("module.", ""), v) for k, v in raw_sd.items())
    model.load_state_dict(clean_sd)
    model.eval()

    output_onnx_path.parent.mkdir(parents=True, exist_ok=True)
    dummy_input = torch.randn(1, 3, 80, 80, dtype=torch.float32)

    print(f"Exporting ONNX model to {output_onnx_path}...")
    torch.onnx.export(
        model,
        dummy_input,
        str(output_onnx_path),
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        dynamo=False,
    )

    # Check ONNX validity
    onnx_model = onnx.load(str(output_onnx_path))
    onnx.checker.check_model(onnx_model)
    print("[OK] ONNX structure validation passed.")

    # Numerical verification against PyTorch outputs
    session = ort.InferenceSession(str(output_onnx_path), providers=["CPUExecutionProvider"])
    max_discrepancy = 0.0

    print(f"Running numerical verification over {num_test_samples} test inputs (tolerance={tolerance})...")
    np.random.seed(42)
    for i in range(num_test_samples):
        inp = np.random.randn(1, 3, 80, 80).astype(np.float32)
        torch_inp = torch.from_numpy(inp)
        with torch.no_grad():
            torch_out = model(torch_inp).numpy()
        onnx_out = session.run(None, {"input": inp})[0]

        diff = float(np.max(np.abs(torch_out - onnx_out)))
        max_discrepancy = max(max_discrepancy, diff)
        print(f"  Sample {i + 1}/{num_test_samples}: max abs diff = {diff:.8e}")
        assert diff <= tolerance, f"Tolerance exceeded on sample {i+1}: {diff} > {tolerance}"

    print(f"[OK] Output verification PASSED (max discrepancy = {max_discrepancy:.8e} <= {tolerance})")

    # Compute SHA-256
    h = hashlib.sha256()
    with open(output_onnx_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    sha256 = h.hexdigest().lower()
    print(f"Converted ONNX SHA-256: {sha256}")
    return sha256


def main():
    parser = argparse.ArgumentParser(description="Convert official MiniFASNetV2 weights to ONNX")
    parser.add_argument("--pth", type=Path, default=Path("models/2.7_80x80_MiniFASNetV2.pth"), help="Path to input .pth")
    parser.add_argument("--out", type=Path, default=Path("models/minifasnet_v2.onnx"), help="Path to output .onnx")
    parser.add_argument("--tolerance", type=float, default=1e-4, help="Max allowed numerical tolerance")
    args = parser.parse_args()

    pth_file = download_official_weights(args.pth)
    sha = convert_and_verify(pth_file, args.out, tolerance=args.tolerance)
    print("Conversion complete.")


if __name__ == "__main__":
    main()
