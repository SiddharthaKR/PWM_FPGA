// tb_events32.vh
// Event-log driven interactive session loop, for DUTs on the 32-bit "sys"
// bus (asg/scope/dsp-top) -- see common/tb_bus32.vh. Same protocol and
// contract as tb_events16.vh (see that file for the full description); the
// only difference is calling write_reg32/read_reg32 instead of the 16-bit
// variants.

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
            write_reg32(ev_a1, ev_a2);
          end else if (ev_cmd == "R") begin
            read_reg32(ev_a1, ev_a2);
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
