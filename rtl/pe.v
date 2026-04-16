`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Top-Level Accelerator
// - Connects controller, loader, systolic array, and output collector.
// - Presents the single-run accelerator interface: start / busy / done / c_valid.
// - Exposes internal buses needed for waveform inspection and trace generation.
// -----------------------------------------------------------------------------
module top #(
    parameter ARRAY_SIZE = 4,
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
) (
    input clk,
    input rst_n,
    input start,
    input [ARRAY_SIZE*ARRAY_SIZE*DATA_WIDTH-1:0] a_matrix_flat,
    input [ARRAY_SIZE*ARRAY_SIZE*DATA_WIDTH-1:0] b_matrix_flat,
    output busy,
    output done,
    output c_valid,
    // Output matrix is flattened in row-major order:
    // flat index = row * ARRAY_SIZE + col.
    output [ARRAY_SIZE*ARRAY_SIZE*ACC_WIDTH-1:0] c_matrix_flat,

    // Controller debug: FSM state code and run-local cycle count.
    output [2:0] dbg_state,
    output [15:0] dbg_cycle,

    // Loader debug: skewed input stream timing and edge-injected operands.
    output [15:0] dbg_stream_cycle,
    output [ARRAY_SIZE*DATA_WIDTH-1:0] dbg_a_row_data_flat,
    output [ARRAY_SIZE-1:0] dbg_a_row_valid,
    output [ARRAY_SIZE*DATA_WIDTH-1:0] dbg_b_col_data_flat,
    output [ARRAY_SIZE-1:0] dbg_b_col_valid,

    // Array / collector debug: PE activity, PE partial sums, and capture event.
    output [ARRAY_SIZE*ARRAY_SIZE*ACC_WIDTH-1:0] dbg_pe_psum_flat,
    output [ARRAY_SIZE*ARRAY_SIZE-1:0] dbg_pe_mac_fire_flat,
    output dbg_c_valid
);

    // Controller control wires.
    wire ctrl_load_en;
    wire ctrl_stream_en;
    wire ctrl_compute_en;
    wire ctrl_clear_acc;
    wire ctrl_collect_en;
    wire [2:0] ctrl_state_dbg;
    wire [15:0] ctrl_cycle_count_dbg;

    // Loader output wires feeding the array edge ports.
    wire [ARRAY_SIZE*DATA_WIDTH-1:0] loader_a_row_data_flat;
    wire [ARRAY_SIZE-1:0] loader_a_row_valid;
    wire [ARRAY_SIZE*DATA_WIDTH-1:0] loader_b_col_data_flat;
    wire [ARRAY_SIZE-1:0] loader_b_col_valid;
    wire [15:0] loader_stream_cycle_dbg;

    // Array outputs for collection and observability.
    wire [ARRAY_SIZE*ARRAY_SIZE*ACC_WIDTH-1:0] array_c_psum_flat;
    wire [ARRAY_SIZE*ARRAY_SIZE-1:0] array_pe_mac_fire_flat;

    wire collector_c_valid;

    controller #(
        .ARRAY_SIZE(ARRAY_SIZE)
    ) u_controller (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .busy(busy),
        .done(done),
        .load_en(ctrl_load_en),
        .stream_en(ctrl_stream_en),
        .compute_en(ctrl_compute_en),
        .clear_acc(ctrl_clear_acc),
        .collect_en(ctrl_collect_en),
        .state_dbg(ctrl_state_dbg),
        .cycle_count_dbg(ctrl_cycle_count_dbg)
    );

    input_loader #(
        .ARRAY_SIZE(ARRAY_SIZE),
        .DATA_WIDTH(DATA_WIDTH)
    ) u_input_loader (
        .clk(clk),
        .rst_n(rst_n),
        .load_en(ctrl_load_en),
        .stream_en(ctrl_stream_en),
        .a_matrix_flat(a_matrix_flat),
        .b_matrix_flat(b_matrix_flat),
        .a_row_data_flat(loader_a_row_data_flat),
        .a_row_valid(loader_a_row_valid),
        .b_col_data_flat(loader_b_col_data_flat),
        .b_col_valid(loader_b_col_valid),
        .stream_cycle_dbg(loader_stream_cycle_dbg)
    );

    systolic_array #(
        .ARRAY_SIZE(ARRAY_SIZE),
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH(ACC_WIDTH)
    ) u_systolic_array (
        .clk(clk),
        .rst_n(rst_n),
        .clear_acc(ctrl_clear_acc),
        .enable(ctrl_compute_en),
        .a_row_data_flat(loader_a_row_data_flat),
        .a_row_valid(loader_a_row_valid),
        .b_col_data_flat(loader_b_col_data_flat),
        .b_col_valid(loader_b_col_valid),
        .c_psum_flat(array_c_psum_flat),
        .pe_mac_fire_flat(array_pe_mac_fire_flat)
    );

    output_collector #(
        .ARRAY_SIZE(ARRAY_SIZE),
        .ACC_WIDTH(ACC_WIDTH)
    ) u_output_collector (
        .clk(clk),
        .rst_n(rst_n),
        .collect_en(ctrl_collect_en),
        .c_psum_flat_in(array_c_psum_flat),
        .c_matrix_flat(c_matrix_flat),
        .c_valid(collector_c_valid)
    );

    // Top-level status and debug wiring. Keeping these as named assigns makes
    // waveforms easier to read than folding everything into instance connections.
    assign c_valid = collector_c_valid;
    assign dbg_state = ctrl_state_dbg;
    assign dbg_cycle = ctrl_cycle_count_dbg;
    assign dbg_stream_cycle = loader_stream_cycle_dbg;
    assign dbg_a_row_data_flat = loader_a_row_data_flat;
    assign dbg_a_row_valid = loader_a_row_valid;
    assign dbg_b_col_data_flat = loader_b_col_data_flat;
    assign dbg_b_col_valid = loader_b_col_valid;
    assign dbg_pe_psum_flat = array_c_psum_flat;
    assign dbg_pe_mac_fire_flat = array_pe_mac_fire_flat;
    assign dbg_c_valid = collector_c_valid;

endmodule
