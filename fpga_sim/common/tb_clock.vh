// tb_clock.vh
// Shared clock/reset generation, included textually into every testbench.
// Every testbench must declare: reg clk; reg rstn;
// 125 MHz clock -> 8ns period (matches pyrpl/fpga/clockInfo.txt / adc_clk domain)

task automatic init_clock;
  begin
    clk = 1'b0;
  end
endtask

always #4 clk = ~clk;  // 8ns period -> 125 MHz

task automatic pulse_reset;
  integer i;
  begin
    rstn = 1'b0;
    for (i = 0; i < 5; i = i + 1) @(posedge clk);
    @(negedge clk);
    rstn = 1'b1;
    for (i = 0; i < 2; i = i + 1) @(posedge clk);
  end
endtask
