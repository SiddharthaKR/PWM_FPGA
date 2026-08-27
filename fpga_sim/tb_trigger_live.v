`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_trigger_block.v -- see
// common/tb_events16.vh and README.md's "Interactive sessions" section.
//
// Poke codes (P <code> <value_hex>):
//   0 = dat_i          1 = phase1_i
// Probe codes (Q <code>):
//   0 = dat_o   1 = signal_o   2 = trig_o

module tb_trigger_live;
  reg clk;
  reg rstn;
  reg signed [13:0] dat_i;
  reg  [13:0] phase1_i;
  wire signed [13:0] dat_o;
  wire signed [13:0] signal_o;
  wire trig_o;

  reg  [15:0] addr;
  reg         wen;
  reg         ren;
  reg  [31:0] wdata;
  wire [31:0] rdata;
  wire        ack;

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"
  `include "common/tb_events16.vh"

  red_pitaya_trigger_block dut (
    .clk_i     (clk),
    .rstn_i    (rstn),
    .dat_i     (dat_i),
    .phase1_i  (phase1_i),
    .dat_o     (dat_o),
    .signal_o  (signal_o),
    .trig_o    (trig_o),
    .addr      (addr),
    .wen       (wen),
    .ren       (ren),
    .ack       (ack),
    .rdata     (rdata),
    .wdata     (wdata)
  );

  task poke_signal;
    input integer code;
    input integer value;
    begin
      @(negedge clk);
      case (code)
        0: dat_i    = value[13:0];
        1: phase1_i = value[13:0];
        default: ;
      endcase
    end
  endtask

  task probe_signal;
    input  integer code;
    output integer value;
    begin
      case (code)
        0: value = dat_o;
        1: value = signal_o;
        2: value = trig_o;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk = 1'b0;
    rstn = 1'b0;
    dat_i = 14'sd0;
    phase1_i = 14'd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    pulse_reset;

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_trigger_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
