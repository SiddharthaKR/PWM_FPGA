`timescale 1ns/1ps

// Testbench for red_pitaya_iq_block.v in isolation (lock-in amplifier /
// NCO+mixer used for e.g. PDH demodulation). Same stimulus.hex / cfg.hex /
// dump.vcd convention as tb_pid.v -- see that file for the rationale.

module tb_iq;
  reg clk;
  reg rstn;
  reg sync_i;
  reg signed [13:0] dat_i;
  wire signed [13:0] dat_o;
  wire signed [13:0] signal_o;
  wire signed [13:0] signal2_o;

  reg  [15:0] addr;
  reg         wen;
  reg         ren;
  reg  [31:0] wdata;
  wire [31:0] rdata;
  wire        ack;

  red_pitaya_iq_block dut (
    .clk_i     (clk),
    .rstn_i    (rstn),
    .sync_i    (sync_i),
    .dat_i     (dat_i),
    .dat_o     (dat_o),
    .signal_o  (signal_o),
    .signal2_o (signal2_o),
    .addr      (addr),
    .wen       (wen),
    .ren       (ren),
    .ack       (ack),
    .rdata     (rdata),
    .wdata     (wdata)
  );

  reg [13:0] stim_mem [0:`N_SAMPLES-1];
  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"

  initial begin
    clk    = 1'b0;
    rstn   = 1'b0;
    sync_i = 1'b0;
    dat_i  = 14'sd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    $readmemh("stimulus.hex", stim_mem);

    pulse_reset;

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
    $dumpvars(0, tb_iq);

    // "on" (tied to sync_i inside red_pitaya_iq_block) must see a 0 before a
    // 1 to zero its NCO phase accumulator: the accumulator's `reg phase` has
    // no reset branch of its own, only an `if (on==0) phase<=0` branch, so
    // if sync_i is held at 1 from the start, `phase` never leaves its
    // uninitialized X. This mirrors pyrpl's own DspModule._synchronize()
    // (pyrpl/hardware_modules/dsp.py), which deliberately pulses the sync
    // register 0->1 for exactly this reason before relying on an iq module.
    @(negedge clk);
    sync_i = 1'b1;
    @(negedge clk);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
      dat_i = stim_mem[i];
    end
    @(negedge clk);
    #40;
    $finish;
  end
endmodule
