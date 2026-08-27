`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_scope.v -- see
// common/tb_events32.vh and README.md's "Interactive sessions" section.
// AXI streaming is tied off exactly as in tb_scope.v (unused here too).
// Buffer contents are read the "real" way with R <addr>, same addresses as
// run_scope.py (0x10000+4*k for channel A, 0x20000+4*k for channel B) --
// see README.md finding #4 for the set_dly >= 2**RSZ requirement before a
// trigger will actually be honored.
//
// Poke codes (P <code> <value_hex>):
//   0 = adc_a_i   1 = adc_b_i   2 = trig_ext_i
// Probe codes (Q <code>):
//   0 = trig_scope_o

module tb_scope_live;
  reg clk;
  reg rstn;
  reg signed [13:0] adc_a_i;
  reg signed [13:0] adc_b_i;
  reg trig_ext_i;
  reg [1:0] trig_asg_i;
  reg trig_dsp_i;
  wire trig_scope_o;

  wire axi0_clk_o, axi0_rstn_o;
  wire [31:0] axi0_waddr_o;
  wire [63:0] axi0_wdata_o;
  wire [7:0] axi0_wsel_o;
  wire axi0_wvalid_o, axi0_wfixed_o;
  wire [3:0] axi0_wlen_o;
  wire axi1_clk_o, axi1_rstn_o;
  wire [31:0] axi1_waddr_o;
  wire [63:0] axi1_wdata_o;
  wire [7:0] axi1_wsel_o;
  wire axi1_wvalid_o, axi1_wfixed_o;
  wire [3:0] axi1_wlen_o;

  reg  [31:0] sys_addr;
  reg  [31:0] sys_wdata;
  reg  [3:0]  sys_sel;
  reg         sys_wen;
  reg         sys_ren;
  wire [31:0] sys_rdata;
  wire        sys_err;
  wire        sys_ack;

  `include "common/tb_clock.vh"
  `include "common/tb_bus32.vh"
  `include "common/tb_events32.vh"

  red_pitaya_scope dut (
    .adc_clk_i     (clk),
    .adc_rstn_i    (rstn),
    .adc_a_i       (adc_a_i),
    .adc_b_i       (adc_b_i),
    .trig_ext_i    (trig_ext_i),
    .trig_asg_i    (trig_asg_i),
    .trig_dsp_i    (trig_dsp_i),
    .trig_scope_o  (trig_scope_o),

    .axi0_clk_o    (axi0_clk_o),   .axi1_clk_o    (axi1_clk_o),
    .axi0_rstn_o   (axi0_rstn_o),  .axi1_rstn_o   (axi1_rstn_o),
    .axi0_waddr_o  (axi0_waddr_o), .axi1_waddr_o  (axi1_waddr_o),
    .axi0_wdata_o  (axi0_wdata_o), .axi1_wdata_o  (axi1_wdata_o),
    .axi0_wsel_o   (axi0_wsel_o),  .axi1_wsel_o   (axi1_wsel_o),
    .axi0_wvalid_o (axi0_wvalid_o),.axi1_wvalid_o (axi1_wvalid_o),
    .axi0_wlen_o   (axi0_wlen_o),  .axi1_wlen_o   (axi1_wlen_o),
    .axi0_wfixed_o (axi0_wfixed_o),.axi1_wfixed_o (axi1_wfixed_o),
    .axi0_werr_i   (1'b0),         .axi1_werr_i   (1'b0),
    .axi0_wrdy_i   (1'b1),         .axi1_wrdy_i   (1'b1),

    .sys_addr      (sys_addr),
    .sys_wdata     (sys_wdata),
    .sys_sel       (sys_sel),
    .sys_wen       (sys_wen),
    .sys_ren       (sys_ren),
    .sys_rdata     (sys_rdata),
    .sys_err       (sys_err),
    .sys_ack       (sys_ack)
  );

  task poke_signal;
    input integer code;
    input integer value;
    begin
      @(negedge clk);
      case (code)
        0: adc_a_i    = value[13:0];
        1: adc_b_i    = value[13:0];
        2: trig_ext_i = value[0];
        default: ;
      endcase
    end
  endtask

  task probe_signal;
    input  integer code;
    output integer value;
    begin
      case (code)
        0: value = trig_scope_o;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    adc_a_i = 14'sd0;
    adc_b_i = 14'sd0;
    trig_ext_i = 1'b0;
    trig_asg_i = 2'b0;
    trig_dsp_i = 1'b0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    pulse_reset;

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_scope_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
