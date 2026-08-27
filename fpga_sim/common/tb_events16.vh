// tb_events16.vh
// Event-log driven interactive session loop, for DUTs on the 16-bit
// "submodule" bus (pid/iq/iir/trigger) -- see common/tb_bus16.vh.
//
// Reads events.txt line by line, one event per line, always exactly 3
// whitespace-separated fields ("<cmd> <hex> <hex>", unused fields zero):
//   W <addr_hex> <data_hex>   write_reg16(addr, data)
//   R <addr_hex> 0            read_reg16(addr) -> appended to results.txt
//   P <code_hex> <value_hex>  poke_signal(code, value) -- testbench-defined
//   Q <code_hex> 0            probe_signal(code) -> appended to results.txt
//   N <n_hex> 0               advance n clock cycles (inputs held constant)
//
// The including testbench must, BEFORE `include`-ing this file, already have
// declared: reg clk; (from tb_clock.vh) and the bus regs from tb_bus16.vh.
// It must also define two tasks *after* the include (forward reference is
// fine -- Verilog resolves all module-level declarations at elaboration):
//   task poke_signal;  input integer code; input integer value; ...
//   task probe_signal; input integer code; output integer value; ...
// mapping small integer codes to this DUT's specific poke/probe targets
// (see each tb_<block>_live.v's header comment for its code table -- the
// matching Python-side name<->code dict lives in each live_<block>.py).

integer ev_file;
integer ev_res_file;
integer ev_scan;
reg [8*8-1:0] ev_cmd;
integer ev_a1, ev_a2;
integer ev_probe_val;
integer ev_k;

task automatic run_event_log;
  begin
    ev_res_file = $fopen("results.txt", "w");
    ev_file = $fopen("events.txt", "r");
    if (ev_file != 0) begin
      ev_scan = 1;
      while (ev_scan != -1) begin
        ev_scan = $fscanf(ev_file, "%s %h %h\n", ev_cmd, ev_a1, ev_a2);
        if (ev_scan == 3) begin
          if (ev_cmd == "W") begin
            write_reg16(ev_a1[15:0], ev_a2);
          end else if (ev_cmd == "R") begin
            read_reg16(ev_a1[15:0], ev_a2);
            $fwrite(ev_res_file, "%0d\n", ev_a2);
          end else if (ev_cmd == "P") begin
            poke_signal(ev_a1, ev_a2);
          end else if (ev_cmd == "Q") begin
            probe_signal(ev_a1, ev_probe_val);
            $fwrite(ev_res_file, "%0d\n", ev_probe_val);
          end else if (ev_cmd == "N") begin
            for (ev_k = 0; ev_k < ev_a1; ev_k = ev_k + 1) @(negedge clk);
          end
        end
      end
      $fclose(ev_file);
    end
    $fclose(ev_res_file);
  end
endtask
