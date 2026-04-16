# Systolic Array Accelerator (RTL + Execution Analysis)

## Highlights
- 4×4 systolic array implemented in Verilog
- cycle-level execution trace logging
- Python-based visualization of hardware behavior

## 1. Overview

This project implements a 4×4 systolic array accelerator in Verilog and analyzes its execution behavior using a Python-based visualization pipeline.

The focus is on building a cycle-accurate hardware design and making its internal dataflow observable beyond conventional waveform inspection.

---

## 2. Motivation

Systolic arrays are a common architecture for matrix multiplication in hardware accelerators due to their regular structure and predictable timing. However, understanding how data propagates through the array at the cycle level is not straightforward.

Waveform-based debugging becomes difficult as system size increases, and internal behavior is not easily interpretable.

This project was developed to:
- implement a clean RTL systolic array
- expose internal signals in a structured way
- analyze execution behavior using visualization rather than raw waveforms

---

## 3. Architecture

### Dataflow

Matrix A is injected row-wise and matrix B is injected column-wise.  
Data propagates diagonally across the processing element (PE) array.

Each PE performs multiply-accumulate operations and forwards inputs to neighboring PEs. Final results are collected after all data has traversed the array.

---

### Processing Element (PE)

Each PE performs:

- multiplication: `a_in × b_in`
- accumulation: `psum += product`
- forwarding of input data to adjacent PEs

Computation is gated by valid signals: enable && a_valid && b_valid

This ensures that only aligned data contributes to the result.

---

## 4. Module Structure

### RTL (rtl/)

- `pe.v`  
  Implements the core multiply-accumulate unit and data forwarding.

- `systolic_array.v`  
  Instantiates and connects PEs into a 2D array.

- `controller.v`  
  Finite state machine controlling execution:
  IDLE → LOAD → STREAM → DRAIN → COLLECT → DONE

- `input_loader.v`  
  Feeds input matrices into the array.

- `output_collector.v`  
  Collects final outputs and generates a pulse-based valid signal.

- `top.v`  
  Integrates all modules into a complete system.

---

### Testbench (tb/)

- `top_tb.v`  
  Drives input stimuli, runs multiple executions, and generates:
  - waveform dump (VCD)
  - cycle-level trace (`trace.csv`)

---

### Visualization (python/)

- `plot_accelerator.py`  
  Parses `trace.csv` and generates plots to analyze execution behavior.

---

## 5. Simulation Flow

### Compile

```bash
iverilog -g2005 -Wall -o sim \
tb/top_tb.v \
rtl/top.v \
rtl/controller.v \
rtl/input_loader.v \
rtl/output_collector.v \
rtl/systolic_array.v \
rtl/pe.v

```
Run
```
vvp sim
```

Outputs
```
top_tb.vcd
```
Waveform for signal-level debugging
```
trace.csv
```
Structured log of cycle-level execution

---

## 6. Visualization
```
python3 python/plot_accelerator.py
```

The script generates plots from simulation logs to provide a higher-level view of execution behavior.

---

## 7. Results

### Controller Execution Flow
Shows FSM transitions over time and highlights key execution phases.

### Wave Propagation Across Array
Visualizes diagonal activation of processing elements, confirming correct systolic dataflow.

### Partial Sum Evolution
Tracks accumulation behavior within a single PE and verifies correct timing of MAC operations.

### Latency Analysis
Observed latency is 13 cycles, compared to the theoretical 12 cycles for a 4×4 array.
The additional cycle is introduced by control logic overhead.

⸻

## 8. Key Observations

	•	Correct systolic behavior appears as diagonal wave propagation across the array
	•	Valid signal alignment is critical for accurate computation
	•	Control logic introduces measurable latency beyond ideal datapath timing
	•	Visualization significantly improves interpretability compared to waveform-only debugging

⸻

## 9. Project Scope

This project focuses on clarity and observability rather than performance optimization.
It is intended as a cycle-accurate reference design for understanding systolic array behavior at the RTL level.

