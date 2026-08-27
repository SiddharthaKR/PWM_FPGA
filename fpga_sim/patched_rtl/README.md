# patched_rtl/

Simulation-only copies of vendor RTL files that need a one-line fix to
*compile* under Icarus Verilog. The real files under
`pyrpl/fpga/rtl/` are never modified -- these copies exist only so this
simulation harness (`pyrpl/fpga/fpga_sim/`) can build.

## red_pitaya_iir_block.v

Original line (still present, unmodified, in the real repo file):

```verilog
$fwrite(fdebug,"%d\n", x0);
```

`fdebug` is a leftover debug file-descriptor identifier -- it is never
declared anywhere in the module (no `integer fdebug;`, no `$fopen`). Icarus
Verilog refuses to elaborate this ("Unable to bind wire/reg/memory
`fdebug` in `<instance>`"), because implicit net inference does not apply to
identifiers used only as a `$fwrite` file-descriptor argument.

This has no effect on any functional signal (`dat_o`, `signal_o`, etc.), so
the patched copy here simply removes that one statement. Real hardware/real
synthesis is unaffected either way -- Vivado does not error on this (it
likely treats it as tool-specific debug output that gets stripped or
ignored), which is presumably why it was never caught before.

## red_pitaya_pid_block.v

With the default `DERIVATIVE=0` parameter, the module-level `reg signed
[39-DSR:0] kd_reg_s` (declared just above the `generate if (DERIVATIVE==1)
... else ...` block, and the one actually referenced by the `pid_sum`
continuous assignment) is never driven -- both generate branches instead
declare and drive their *own* same-named `kd_reg_s` in a nested generate
scope, which shadows but does not connect to the outer declaration. An
undriven `reg` simulates as X forever in Icarus, which poisons
`pid_sum`/`pid_out`/`dat_o` for the entire run (harmless in real synthesis,
where an unconnected net like this is simply optimized to a constant 0).

`tb_pid.v` (single instance) works around this with a one-time hierarchical
deposit (`dut.kd_reg_s = 0;`) instead of using this patched copy, since that
is even less invasive for a single, easily-addressed instance. This patched
copy exists for `tb_dsp_top.v`, where 3 PID instances are created inside an
unnamed `generate for` loop (auto-numbered hierarchical paths like
`genblk1[0]`, `genblk1[1]`, ... by Icarus) -- fixing it once at the source
with an `initial kd_reg_s = 0;` (a no-op for real synthesis) is more robust
than guessing at generated instance path names.
