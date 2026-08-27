`timescale 1ns/1ps

// Testbench for red_pitaya_asg.v in isolation (arbitrary waveform
// generator). Configuration (control word, amplitude/dc, size/step/offset,
// and the waveform table itself) is all driven from cfg.hex as
// "<addr_hex> <data_hex>" pairs (32-bit sys bus), same mechanism as the
// other testbenches' register config -- just with many more lines here
// since the waveform table is programmed the same way. No stimulus.hex is
// needed since this block only generates output, it has no dat_i input.

module tb_asg;
  reg clk;
  reg rstn;
  wire [13:0] dac_a_o;
  wire [13:0] dac_b_o;
  reg trig_a_i, trig_b_i;
  wire [1:0] trig_out_o;
  reg trig_scope_i;
  wire [13:0] asg1phase_o;

  reg  [31:0] sys_addr;
  reg  [31:0] sys_wdata;
  reg  [3:0]  sys_sel;
  reg         sys_wen;
  reg         sys_ren;
  wire [31:0] sys_rdata;
  wire        sys_err;
  wire        sys_ack;

  red_pitaya_asg dut (
    .dac_a_o      (dac_a_o),
    .dac_b_o      (dac_b_o),
    .dac_clk_i    (clk),
    .dac_rstn_i   (rstn),
    .trig_a_i     (trig_a_i),
    .trig_b_i     (trig_b_i),
    .trig_out_o   (trig_out_o),
    .trig_scope_i (trig_scope_i),
    .asg1phase_o  (asg1phase_o),
    .sys_addr     (sys_addr),
    .sys_wdata    (sys_wdata),
    .sys_sel      (sys_sel),
    .sys_wen      (sys_wen),
    .sys_ren      (sys_ren),
    .sys_rdata    (sys_rdata),
    .sys_err      (sys_err),
    .sys_ack      (sys_ack)
  );

  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;

  `include "common/tb_clock.vh"
  `include "common/tb_bus32.vh"

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    trig_a_i = 1'b0;
    trig_b_i = 1'b0;
    trig_scope_i = 1'b0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    pulse_reset;

    cfg_file = $fopen("cfg.hex", "r");
    if (cfg_file != 0) begin
      scan_ok = 1;
      while (scan_ok != -1) begin
        scan_ok = $fscanf(cfg_file, "%h %h\n", caddr, cdata);
        if (scan_ok == 2) write_reg32(caddr, cdata);
      end
      $fclose(cfg_file);
    end

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_asg);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
    end
    #40;
    $finish;
  end
endmodule
