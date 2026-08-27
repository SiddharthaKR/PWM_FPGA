`timescale 1ns/1ps

// Testbench for red_pitaya_dsp.v -- the full DSP crossbar tying together
// PID0-2, Trig, IIR, IQ0-2, and the ADC/DAC/ASG/PWM routing/summing logic.
// Drives two independent "ADC" stimulus records into dat_a_i/dat_b_i, all
// register configuration (input_select/output_select routing + per-module
// PID gains) comes from cfg.hex, same convention as the other testbenches.

module tb_dsp_top;
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

  reg [13:0] stim_a_mem [0:`N_SAMPLES-1];
  reg [13:0] stim_b_mem [0:`N_SAMPLES-1];
  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;

  `include "common/tb_clock.vh"
  `include "common/tb_bus32.vh"

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    dat_a_i = 14'sd0;
    dat_b_i = 14'sd0;
    asg1_i = 14'd0; asg2_i = 14'd0; asg1phase_i = 14'd0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    $readmemh("stimulus_a.hex", stim_a_mem);
    $readmemh("stimulus_b.hex", stim_b_mem);

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
    $dumpvars(0, tb_dsp_top);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
      dat_a_i = stim_a_mem[i];
      dat_b_i = stim_b_mem[i];
    end
    @(negedge clk);
    #40;
    $finish;
  end
endmodule
