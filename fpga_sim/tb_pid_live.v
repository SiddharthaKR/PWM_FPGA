`timescale 1ns/1ps

// Interactive-session testbench for red_pitaya_pid_block.v -- see
// common/tb_events16.vh for the event-log protocol, and README.md's
// "Interactive sessions" section for the full explanation. Same DUT wiring
// and kd_reg_s workaround as tb_pid.v (see that file for why).
//
// Poke codes (P <code> <value_hex>):
//   0 = dat_i          1 = diff_dat_i          2 = sync_i
// Probe codes (Q <code>):
//   0 = dat_o   1 = error   2 = int_shr   3 = pid_out   4 = kp_reg

module tb_pid_live;
  reg clk;
  reg rstn;
  reg sync_i;
  reg signed [13:0] dat_i;
  wire signed [13:0] dat_o;
  reg signed [13:0] diff_dat_i;
  wire signed [13:0] diff_dat_o;

  reg  [15:0] addr;
  reg         wen;
  reg         ren;
  reg  [31:0] wdata;
  wire [31:0] rdata;
  wire        ack;

  `include "common/tb_clock.vh"
  `include "common/tb_bus16.vh"
  `include "common/tb_events16.vh"

  red_pitaya_pid_block dut (
    .clk_i      (clk),
    .rstn_i     (rstn),
    .sync_i     (sync_i),
    .dat_i      (dat_i),
    .dat_o      (dat_o),
    .diff_dat_i (diff_dat_i),
    .diff_dat_o (diff_dat_o),
    .addr       (addr),
    .wen        (wen),
    .ren        (ren),
    .ack        (ack),
    .rdata      (rdata),
    .wdata      (wdata)
  );

  task poke_signal;
    input integer code;
    input integer value;
    begin
      @(negedge clk);
      case (code)
        0: dat_i      = value[13:0];
        1: diff_dat_i = value[13:0];
        2: sync_i     = value[0];
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
        1: value = dut.error;
        2: value = dut.int_shr;
        3: value = dut.pid_out;
        4: value = dut.kp_reg;
        default: value = 32'h0;
      endcase
    end
  endtask

  initial begin
    clk        = 1'b0;
    rstn       = 1'b0;
    sync_i     = 1'b1;
    diff_dat_i = 14'sd0;
    dat_i      = 14'sd0;
    addr = 0; wen = 0; ren = 0; wdata = 0;

    pulse_reset;
    dut.kd_reg_s = 0;  // see tb_pid.v for why this is needed

    $dumpfile("dump.vcd");
    $dumpvars(0, tb_pid_live);

    run_event_log;

    #40;
    $finish;
  end
endmodule
