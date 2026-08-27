"""iverilog/vvp invocation helper."""

import pathlib
import subprocess

# fpga_sim/common/runner.py -> fpga_sim/ -> fpga/ -> fpga/rtl/
RTL_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "rtl"


class SimError(RuntimeError):
    pass


def compile(dut_files, tb_file, workdir, defines=None, include_dirs=None):
    """Compile `dut_files` (filenames relative to RTL_DIR, or absolute/
    relative paths used as-is -- e.g. a patched_rtl/ copy) + `tb_file` with
    iverilog. Returns the path to the compiled workdir/sim.vvp.

    defines: optional dict of preprocessor defines passed as -D NAME=value.
    """
    workdir = pathlib.Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    files = [str(f) if pathlib.Path(f).is_absolute() else str(RTL_DIR / f) for f in dut_files]
    files.append(str(tb_file))

    define_args = []
    for k, v in (defines or {}).items():
        define_args += ["-D", f"{k}={v}"]
    include_args = []
    for d in include_dirs or []:
        include_args += ["-I", str(d)]

    vvp_path = workdir / "sim.vvp"
    compile_cmd = ["iverilog", "-g2012", "-o", str(vvp_path)] + define_args + include_args + files
    proc = subprocess.run(compile_cmd, cwd=str(workdir), capture_output=True, text=True)
    if proc.returncode != 0:
        raise SimError(f"iverilog compile failed (cmd={compile_cmd}):\n{proc.stdout}\n{proc.stderr}")
    if proc.stderr.strip():
        print("--- iverilog warnings ---")
        print(proc.stderr)
    return vvp_path


def run_vvp(vvp_path, workdir, vvp_args=None, require_vcd=True, verbose=True):
    """Run an already-compiled sim.vvp inside `workdir` (so relative
    $readmemh/$fopen/$dumpfile paths resolve there). Returns
    workdir/dump.vcd if require_vcd (the usual case), else None.

    verbose=False suppresses the normal "--- vvp output ---" echo (used by
    Session, which calls this once per interactive command -- printing the
    VCD-open/$finish boilerplate every time would bury the actual result).
    """
    workdir = pathlib.Path(workdir)
    run_cmd = ["vvp", str(vvp_path)] + (vvp_args or [])
    proc = subprocess.run(run_cmd, cwd=str(workdir), capture_output=True, text=True)
    if verbose:
        print("--- vvp output ---")
        print(proc.stdout)
    if proc.returncode != 0:
        raise SimError(f"vvp run failed:\n{proc.stdout}\n{proc.stderr}")

    if not require_vcd:
        return None
    vcd_path = workdir / "dump.vcd"
    if not vcd_path.exists():
        raise SimError(f"Expected {vcd_path} was not produced. vvp stdout:\n{proc.stdout}")
    return vcd_path


def compile_and_run(dut_files, tb_file, workdir, defines=None, vvp_args=None, include_dirs=None):
    """Convenience wrapper: compile() then run_vvp(). Returns the vcd path."""
    vvp_path = compile(dut_files, tb_file, workdir, defines=defines, include_dirs=include_dirs)
    return run_vvp(vvp_path, workdir, vvp_args=vvp_args)
