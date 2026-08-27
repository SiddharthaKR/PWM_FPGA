`timescale 1ns/1ps

// Testbench for red_pitaya_iir_block.v in isolation (general biquad-style
// IIR filter, coefficients loaded through a small memory-mapped RAM). Same
// stimulus.hex / cfg.hex / dump.vcd convention as tb_pid.v.
//
// NOTE: the vendor RTL contains an unrelated leftover debug statement,
// `$fwrite(fdebug, "%d\n", x0);`, that references an undeclared `fdebug`
// identifier (silently becomes an implicit 1-bit net, per Verilog's default
// nettype rules). It has no effect on dat_o/signal_o and is harmless here.

module tb_iir;
  reg clk;
  reg rstn;
  reg signed [13:0] dat_i;
  wire signed [13:0] dat_o;

  reg  [15:0] addr;
  reg         wen;
  reg         ren;
  reg  [31:0] wdata;
  wire [31:0] rdata;
  wire        ack;

  red_pitaya_iir_block dut (
    .clk_i  (clk),
    .rstn_i (rstn),
    .dat_i  (dat_i),
    .dat_o  (dat_o),
    .addr   (addr),
    .wen    (wen),
    .ren    (ren),
    .ack    (ack),
    .rdata  (rdata),
    .wdata  (wdata)
  );

  reg [13:0] stim_mem [0:`N_SAMPLES-1];
  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"

  initial begin
    clk  = 1'b0;
    rstn = 1'b0;
    dat_i = 14'sd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    $readmemh("stimulus.hex", stim_mem);

    pulse_reset;
    // dut's `on` register resets to 0, so the history-clearing branch of the
    // main always block (see red_pitaya_iir_block.v: `if (on==1'b0) ...`)
    // has already run continuously since reset -- unlike the IQ block, no
    // extra sync pulse is needed here, only the ordinary reset pulse above.

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
    $dumpvars(0, tb_iir);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
      dat_i = stim_mem[i];
    end
    @(negedge clk);
    #40;
    $finish;
  end
endmodule
