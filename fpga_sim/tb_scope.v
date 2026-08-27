`timescale 1ns/1ps

// Testbench for red_pitaya_scope.v in isolation (ADC acquisition buffer with
// arm/trigger/decimation logic). Feeds stimulus.hex into adc_a_i (same as
// tb_pid.v), applies cfg.hex register writes, then -- once capture should be
// complete -- issues real sys-bus reads to pull back CAPTURE_LEN samples of
// the channel-A ring buffer (address 0x10000 + 4*k) and writes them as plain
// decimal text to readback.txt, one value per line, for the Python side to
// compare against the driven stimulus. AXI streaming (axi0/axi1) is left
// disabled (set_a_axi_en/set_b_axi_en default to 0 on reset) and its input
// ports are tied to safe constants since it is not exercised here.

module tb_scope;
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

  reg [13:0] stim_mem [0:`N_SAMPLES-1];
  integer i;
  integer cfg_file;
  integer caddr, cdata, scan_ok;
  integer readback_file;
  reg [31:0] rval;

  `include "common/tb_clock.vh"
  `include "common/tb_bus32.vh"

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    adc_a_i = 14'sd0;
    adc_b_i = 14'sd0;
    trig_ext_i = 1'b0;
    trig_asg_i = 2'b0;
    trig_dsp_i = 1'b0;
    sys_addr = 0; sys_wdata = 0; sys_sel = 4'hF; sys_wen = 0; sys_ren = 0;

    $readmemh("stimulus.hex", stim_mem);

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
    $dumpvars(0, tb_scope);

    for (i = 0; i < `N_SAMPLES; i = i + 1) begin
      @(negedge clk);
      adc_a_i = stim_mem[i];
      adc_b_i = stim_mem[i];
    end
    @(negedge clk);
    #40;

    // read back CAPTURE_LEN samples of the channel-A ring buffer
    readback_file = $fopen("readback.txt", "w");
    for (i = 0; i < `CAPTURE_LEN; i = i + 1) begin
      read_reg32(32'h10000 + 4*i, rval);
      $fwrite(readback_file, "%0d\n", rval[13:0]);
    end
    $fclose(readback_file);

    $finish;
  end
endmodule
