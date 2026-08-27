# Interactive session walkthrough

A hands-on "what do I actually type" companion to the "Interactive
sessions" section in `README.md`. Uses the PID block as the example --
the same pattern (`sim.write`/`sim.read`/`sim.poke`/`sim.probe`/`sim.run`)
applies to every `live_<block>.py`.

## Start a session

```
cd pyrpl/fpga/fpga_sim
python -i live_pid.py
```

This runs `live_pid.py`'s own short demo, then drops you at a Python
prompt with the `sim` object (and `regbridge`, `session`) still available.
Everything below is typed at that prompt.

## 1. Read a register

```python
>>> sim.read(regbridge.PidRegs.ADDR_KP)
4096          # raw fixed-point int; p = 4096/4096 = 1.0
```

## 2. Write a register, then read it back

```python
>>> sim.write(regbridge.PidRegs.ADDR_KP, regbridge.PidRegs.p(0.25))
>>> sim.read(regbridge.PidRegs.ADDR_KP)
1024          # 0.25 * 4096
```

## 3. Poke an input, run some cycles, see the output move

```python
>>> sim.poke('dat_i', regbridge.encode_signed(0.8, 14, 2**13))
>>> sim.run(15)                                   # let the pipeline settle
>>> round(session.decode(sim.probe('dat_o'), 14, 2**13), 4)
0.2           # matches p=0.25 * dat_i=0.8 (fixed-point, so exactly 0.19995... before rounding)
```

## 4. Change a register mid-session and watch the output respond

No restart needed -- this is the whole point of the interactive session
over the batch `run_pid.py` demo.

```python
>>> sim.write(regbridge.PidRegs.ADDR_KP, regbridge.PidRegs.p(1.0))
>>> sim.run(15)
>>> round(session.decode(sim.probe('dat_o'), 14, 2**13), 4)
0.8           # same input, now p=1.0
```

## 5. Poke a custom/undocumented address

Nothing restricts `read`/`write` to registers this harness already knows
about -- that's the point.

```python
>>> sim.read(0x999)
0             # whatever the RTL's default case returns
```

## 6. Snapshot several signals at once

Like glancing at a live dashboard instead of one probe at a time.

```python
>>> sim.snapshot(['dat_o', 'error', 'int_shr', 'pid_out'])
{'dat_o': 6554, 'error': 6554, 'int_shr': 0, 'pid_out': 6554}
```

## 7. Full waveform review afterward

Every call is recorded in one continuous VCD, even across many interactive
commands -- load it the same way the batch demos do:

```python
>>> import vcdtools, plotting
>>> parsed = vcdtools.parse_vcd(sim.vcd_path())
>>> t = parsed[vcdtools.find(parsed, '.clk')]  # etc, same API as run_pid.py
```

## Doing this for another block

Same commands, different script and poke/probe names:

```
python -i live_iq.py
python -i live_iir.py
python -i live_trigger.py
python -i live_asg.py
python -i live_scope.py
python -i live_dsp_crossbar.py
```

Each `tb_<block>_live.v`'s header comment lists that block's exact poke/probe
name table (which signals you can `poke`/`probe` by name, vs. needing a raw
`write`/`read` address for anything else).
