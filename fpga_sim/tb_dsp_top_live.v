`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_dsp.v (the full crossbar) --
// see common/tb_events32.vh and README.md's "Interactive sessions" section.
// Uses the same patched_rtl/red_pitaya_pid_block.v copy as tb_dsp_top.v
// (needed for 3 PID instances inside an unnamed generate loop -- see
// patched_rtl/README.md).
//
// Poke codes (P <code> <value_hex>):
//   0 = dat_a_i   1 = dat_b_i   2 = asg1_i   3 = asg2_i
// Probe codes (Q <code>):
//   0 = dat_a_o   1 = dat_b_o   2 = trig_o   3 = scope1_o   4 = scope2_o

module tb_dsp_top_live;
  reg clk;
  reg rstn;
  reg signed [13:0] dat_a_i, dat_b_i;
  wire signed [13:0] dat_a_o, dat_b_o;
  wire [13:0] scope1_o, scope2_o;
  reg  [13:0] asg1_i, asg2_i;
  reg  [13:0] asg1phase_i;
  wire [13:0] pwm0, pwm1, pwm2, pwm3;
  wire trig_o;

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

  red_pitaya_dsp dut (
    .clk_i        (clk),
    .rstn_i       (rstn),
    .dat_a_i      (dat_a_i),
    .dat_b_i      (dat_b_i),
    .dat_a_o      (dat_a_o),
    .dat_b_o      (dat_b_o),
    .scope1_o     (scope1_o),
    .scope2_o     (scope2_o),
    .asg1_i       (asg1_i),
    .asg2_i       (asg2_i),
    .asg1phase_i  (asg1phase_i),
    .pwm0         (pwm0),
    .pwm1         (pwm1),
    .pwm2         (pwm2),
    .pwm3         (pwm3),
    .trig_o       (trig_o),
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
        0: dat_a_i = value[13:0];
        1: dat_b_i = value[13:0];
        2: asg1_i  = value[13:0];
        3: asg2_i  = value[13:0];
        default: ;
      endcase
    end
  endtask

  task probe_signal;
    input  integer code;
    output integer value;
    begin
      case (code)
        0: value = dat_a_o;
        1: value = dat_b_o;
        2: value = trig_o;
        3: value = scope1_o;
        4: value = scope2_o;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    dat_a_i = 14'sd0;
    dat_b_i = 14'sd0;
    asg1_i = 14'd0; asg2_i = 14'd0; asg1phase_i = 14'd0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    pulse_reset;

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_dsp_top_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
