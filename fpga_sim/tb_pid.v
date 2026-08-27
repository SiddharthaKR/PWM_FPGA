`timescale 1ns/1ps

// Testbench for red_pitaya_pid_block.v in isolation.
// Feeds a stimulus record (stimulus.hex, one 14-bit two's-complement hex
// sample per line) into dat_i, one sample per clock cycle, after applying
// register writes listed in cfg.hex ("<addr_hex> <data_hex>" per line,
// applied while rstn is still low so they survive the module's reset).
// Dumps the full DUT hierarchy to dump.vcd so internal signals (error,
// int_reg, kp_reg, pid_out, ...) are visible to the Python side.

module tb_pid;
  reg clk;
  reg rstn;
  reg sync_i;
  reg signed [13:0] dat_i;
  wire signed [13:0] dat_o;
  reg signed [13:0] diff_dat_i;
  wire signed [13:0] diff_dat_o;

  reg  [15:0] addr;
  reg         wen;
  reg         ren;
  reg  [31:0] wdata;
  wire [31:0] rdata;
  wire        ack;

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"

  red_pitaya_pid_block dut (
    .clk_i      (clk),
    .rstn_i     (rstn),
    .sync_i     (sync_i),
    .dat_i      (dat_i),
    .dat_o      (dat_o),
    .diff_dat_i (diff_dat_i),
    .diff_dat_o (diff_dat_o),
    .addr       (addr),
    .wen        (wen),
    .ren        (ren),
    .ack        (ack),
    .rdata      (rdata),
    .wdata      (wdata)
  );

  reg [13:0] stim_mem [0:`N_SAMPLES-1];
  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;

  initial begin
    clk        = 1'b0;
    rstn       = 1'b0;
    sync_i     = 1'b1;
    diff_dat_i = 14'sd0;
    dat_i      = 14'sd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    $readmemh("stimulus.hex", stim_mem);

    // apply register configuration BEFORE releasing reset is fine too, but
    // the pid_block's reset only clears register state on rstn==0, so we
    // configure after the reset pulse to guarantee our values stick.
    pulse_reset;

    // Simulation-only workaround for a dead-code artifact in
    // red_pitaya_pid_block.v: with the default DERIVATIVE==0 parameter, the
    // module-level `reg signed [39-DSR:0] kd_reg_s` (declared just above the
    // `generate if (DERIVATIVE==1) ... else ...` block, and the one actually
    // referenced by the `pid_sum` continuous assignment) is never driven --
    // both generate branches instead declare and drive their *own* local
    // `kd_reg_s` in a nested generate scope, which shadows but does not
    // connect to the outer declaration. An undriven `reg` in Icarus
    // simulates as X forever, and X propagates through `pid_sum` and poisons
    // `pid_out`/`dat_o` for the entire run. In real synthesis an unconnected
    // net like this is simply optimized to a constant 0 by Vivado, so this
    // is purely a simulation artifact -- harmless on real hardware, but
    // fatal for RTL simulation unless worked around. Since nothing in the
    // real design ever drives it either, a single deposit to 0 right after
    // reset is a faithful (and minimal) fix.
    dut.kd_reg_s = 0;

    cfg_file = $fopen("cfg.hex", "r");
    if (cfg_file != 0) begin
      scan_ok = 1;
      while (scan_ok != -1) begin
        scan_ok = $fscanf(cfg_file, "%h %h\n", caddr, cdata);
        if (scan_ok == 2) write_reg16(caddr[15:0], cdata[31:0]);
      end
      $fclose(cfg_file);
    end

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_pid);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
      dat_i = stim_mem[i];
    end
    @(negedge clk);
    #40;
    $finish;
  end
endmodule
