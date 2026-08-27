// tb_bus16.vh
// Bus tasks for the "submodule" 16-bit address system bus used by
// red_pitaya_pid_block / red_pitaya_iq_block / red_pitaya_iir_block /
// red_pitaya_trigger_block (addr/wen/ren/ack/rdata/wdata).
//
// Every testbench that includes this file must declare, with exactly these
// names: reg clk; reg [15:0] addr; reg wen; reg ren; reg [31:0] wdata;
// wire [31:0] rdata; wire ack;

task automatic write_reg16;
  input [15:0] a;
  input [31:0] d;
  begin
    @(negedge clk);
    addr  = a;
    wdata = d;
    wen   = 1'b1;
    ren   = 1'b0;
    @(negedge clk);
    wen   = 1'b0;
  end
endtask

task automatic read_reg16;
  input  [15:0] a;
  output [31:0] result;
  begin
    @(negedge clk);
    addr = a;
    ren  = 1'b1;
    wen  = 1'b0;
    @(negedge clk);
    result = rdata;
    ren  = 1'b0;
  end
endtask
