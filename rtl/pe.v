`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Processing Element (PE)
// - Performs one signed multiply-accumulate for the output-stationary array.
// - Forwards A to the right and B downward through registered outputs.
// - Keeps the local partial sum resident in the PE across the full run.
// -----------------------------------------------------------------------------
module pe #(
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
) (
    input clk,
    input rst_n,
    input clear_acc,
    input enable,
    input signed [DATA_WIDTH-1:0] a_in,
    input signed [DATA_WIDTH-1:0] b_in,
    input a_valid_in,
    input b_valid_in,
    output reg signed [DATA_WIDTH-1:0] a_out,
    output reg signed [DATA_WIDTH-1:0] b_out,
    output reg a_valid_out,
    output reg b_valid_out,
    output reg signed [ACC_WIDTH-1:0] psum_out,
    output wire mac_fire
);

    wire signed [(2*DATA_WIDTH)-1:0] mult_result;
    wire signed [ACC_WIDTH-1:0] mult_result_ext;

    initial begin
        // The product must fit before it is sign-extended into the accumulator.
        if (ACC_WIDTH < (2 * DATA_WIDTH)) begin
            $fatal(1, "ACC_WIDTH must be >= 2*DATA_WIDTH");
        end
    end

    assign mult_result = a_in * b_in;
    assign mult_result_ext = {{(ACC_WIDTH-(2*DATA_WIDTH)){mult_result[(2*DATA_WIDTH)-1]}}, mult_result};
    // A MAC is meaningful only when compute is enabled and both forwarded operands are valid.
    assign mac_fire = enable && a_valid_in && b_valid_in;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_out       <= {DATA_WIDTH{1'b0}};
            b_out       <= {DATA_WIDTH{1'b0}};
            a_valid_out <= 1'b0;
            b_valid_out <= 1'b0;
            psum_out    <= {ACC_WIDTH{1'b0}};
        end else begin
            // Registered forwarding keeps the systolic data movement aligned cycle by cycle.
            a_out       <= a_in;
            b_out       <= b_in;
            a_valid_out <= a_valid_in;
            b_valid_out <= b_valid_in;

            // clear_acc starts a new output accumulation window for this PE.
            if (clear_acc) begin
                psum_out <= {ACC_WIDTH{1'b0}};
            end else if (mac_fire) begin
                // Output-stationary dataflow keeps the partial sum local while operands move.
                psum_out <= psum_out + mult_result_ext;
            end
        end
    end

endmodule
