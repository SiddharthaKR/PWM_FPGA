// tb_bus32.vh
// Bus tasks for the top-level 32-bit "sys" bus used by red_pitaya_asg,
// red_pitaya_scope and red_pitaya_dsp (sys_addr/sys_wdata/sys_sel/sys_wen/
// sys_ren/sys_rdata/sys_err/sys_ack).
//
// Every testbench that includes this file must declare, with exactly these
// names: reg clk; reg [31:0] sys_addr; reg [31:0] sys_wdata; reg [3:0] sys_sel;
// reg sys_wen; reg sys_ren; wire [31:0] sys_rdata; wire sys_err; wire sys_ack;

task automatic write_reg32;
  input [31:0] a;
  input [31:0] d;
  begin
    @(negedge clk);
    sys_addr  = a;
    sys_wdata = d;
    sys_sel   = 4'hF;
    sys_wen   = 1'b1;
    sys_ren   = 1'b0;
    @(negedge clk);
    sys_wen   = 1'b0;
  end
endtask

task automatic read_reg32;
  input  [31:0] a;
  output [31:0] result;
  begin
    @(negedge clk);
    sys_addr = a;
    sys_ren  = 1'b1;
    sys_wen  = 1'b0;
    @(negedge clk);
    result = sys_rdata;
    sys_ren  = 1'b0;
  end
endtask
