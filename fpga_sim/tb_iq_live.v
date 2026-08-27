`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_iq_block.v -- see
// common/tb_events16.vh for the event-log protocol and README.md's
// "Interactive sessions" section.
//
// IMPORTANT (see README.md finding #2 / tb_iq.v): sync_i starts LOW here
// (matching real reset behavior) and the NCO's phase accumulator only
// zeros itself while sync_i==0. You must POKE sync_i to 0 then to 1 at
// least once before the demodulator/modulator will produce anything but X
// -- try it yourself: `sim.poke('sync_i', 0); sim.poke('sync_i', 1)`.
//
// Poke codes (P <code> <value_hex>):
//   0 = dat_i          1 = sync_i
// Probe codes (Q <code>):
//   0 = dat_o   1 = signal_o   2 = signal2_o

module tb_iq_live;
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

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"
  `include "common/tb_events16.vh"

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

  task poke_signal;
    input integer code;
    input integer value;
    begin
      @(negedge clk);
      case (code)
        0: dat_i  = value[13:0];
        1: sync_i = value[0];
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
        2: value = signal2_o;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk    = 1'b0;
    rstn   = 1'b0;
    sync_i = 1'b0;
    dat_i  = 14'sd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    pulse_reset;

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_iq_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
