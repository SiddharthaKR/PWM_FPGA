`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_asg.v -- see
// common/tb_events32.vh and README.md's "Interactive sessions" section.
// ASG has no dat_i (it's a generator, not a filter); pokes only cover its
// trigger inputs.
//
// Poke codes (P <code> <value_hex>):
//   0 = trig_a_i   1 = trig_b_i   2 = trig_scope_i
// Probe codes (Q <code>):
//   0 = dac_a_o   1 = dac_b_o   2 = trig_out_o

module tb_asg_live;
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

  `include "common/tb_clock.vh"
  `include "common/tb_bus32.vh"
  `include "common/tb_events32.vh"

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

  task poke_signal;
    input integer code;
    input integer value;
    begin
      @(negedge clk);
      case (code)
        0: trig_a_i     = value[0];
        1: trig_b_i     = value[0];
        2: trig_scope_i = value[0];
        default: ;
      endcase
    end
  endtask

  task probe_signal;
    input  integer code;
    output integer value;
    begin
      case (code)
        0: value = dac_a_o;
        1: value = dac_b_o;
        2: value = trig_out_o;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    trig_a_i = 1'b0;
    trig_b_i = 1'b0;
    trig_scope_i = 1'b0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    pulse_reset;

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_asg_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
