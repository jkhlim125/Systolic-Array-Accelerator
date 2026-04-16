`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Systolic Array
// - Instantiates the 2D PE mesh for matrix multiplication.
// - Injects A from the left edge and B from the top edge.
// - Exposes every PE partial sum and MAC event for observability.
// -----------------------------------------------------------------------------
module systolic_array #(
    parameter ARRAY_SIZE = 4,
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
) (
    input clk,
    input rst_n,
    input clear_acc,
    input enable,
    input [ARRAY_SIZE*DATA_WIDTH-1:0] a_row_data_flat,
    input [ARRAY_SIZE-1:0] a_row_valid,
    input [ARRAY_SIZE*DATA_WIDTH-1:0] b_col_data_flat,
    input [ARRAY_SIZE-1:0] b_col_valid,
    output [ARRAY_SIZE*ARRAY_SIZE*ACC_WIDTH-1:0] c_psum_flat,
    output [ARRAY_SIZE*ARRAY_SIZE-1:0] pe_mac_fire_flat
);

    genvar row;
    genvar col;

    // A operands propagate horizontally across the array.
    wire signed [DATA_WIDTH-1:0] a_bus [0:ARRAY_SIZE-1][0:ARRAY_SIZE];
    wire                         a_valid_bus [0:ARRAY_SIZE-1][0:ARRAY_SIZE];

    // B operands propagate vertically across the array.
    wire signed [DATA_WIDTH-1:0] b_bus [0:ARRAY_SIZE][0:ARRAY_SIZE-1];
    wire                         b_valid_bus [0:ARRAY_SIZE][0:ARRAY_SIZE-1];

    // Each PE keeps one output-stationary accumulator and a per-cycle MAC activity bit.
    wire signed [ACC_WIDTH-1:0]  pe_psum [0:ARRAY_SIZE-1][0:ARRAY_SIZE-1];
    wire                         pe_mac_fire [0:ARRAY_SIZE-1][0:ARRAY_SIZE-1];

    generate
        for (row = 0; row < ARRAY_SIZE; row = row + 1) begin : GEN_A_EDGE
            // a_row_data_flat is row-major over rows:
            // slice row*DATA_WIDTH +: DATA_WIDTH feeds the left edge of row 'row'.
            assign a_bus[row][0] = a_row_data_flat[(row*DATA_WIDTH) +: DATA_WIDTH];
            assign a_valid_bus[row][0] = a_row_valid[row];
        end

        for (col = 0; col < ARRAY_SIZE; col = col + 1) begin : GEN_B_EDGE
            // b_col_data_flat is column-indexed at the top edge:
            // slice col*DATA_WIDTH +: DATA_WIDTH feeds the top of column 'col'.
            assign b_bus[0][col] = b_col_data_flat[(col*DATA_WIDTH) +: DATA_WIDTH];
            assign b_valid_bus[0][col] = b_col_valid[col];
        end

        for (row = 0; row < ARRAY_SIZE; row = row + 1) begin : GEN_ROWS
            for (col = 0; col < ARRAY_SIZE; col = col + 1) begin : GEN_COLS
                pe #(
                    .DATA_WIDTH(DATA_WIDTH),
                    .ACC_WIDTH(ACC_WIDTH)
                ) u_pe (
                    .clk(clk),
                    .rst_n(rst_n),
                    .clear_acc(clear_acc),
                    .enable(enable),
                    .a_in(a_bus[row][col]),
                    .b_in(b_bus[row][col]),
                    .a_valid_in(a_valid_bus[row][col]),
                    .b_valid_in(b_valid_bus[row][col]),
                    .a_out(a_bus[row][col+1]),
                    .b_out(b_bus[row+1][col]),
                    .a_valid_out(a_valid_bus[row][col+1]),
                    .b_valid_out(b_valid_bus[row+1][col]),
                    .psum_out(pe_psum[row][col]),
                    .mac_fire(pe_mac_fire[row][col])
                );

                // Flatten PE outputs in row-major order:
                // flat index = row * ARRAY_SIZE + col.
                assign c_psum_flat[((row*ARRAY_SIZE + col)*ACC_WIDTH) +: ACC_WIDTH] = pe_psum[row][col];
                assign pe_mac_fire_flat[row*ARRAY_SIZE + col] = pe_mac_fire[row][col];
            end
        end
    endgenerate

endmodule
