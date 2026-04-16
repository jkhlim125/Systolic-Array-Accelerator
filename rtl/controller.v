`timescale 1ns / 1ps

// -----------------------------------------------------------------------------
// Controller
// - Orchestrates one accelerator run from load through collection.
// - Separates STREAM from DRAIN so in-flight operands can finish the mesh.
// - Exposes FSM state and cycle count for debug and trace generation.
// -----------------------------------------------------------------------------
module controller #(
    parameter ARRAY_SIZE = 4
) (
    input clk,
    input rst_n,
    input start,
    output reg busy,
    output reg done,
    output reg load_en,
    output reg stream_en,
    output reg compute_en,
    output reg clear_acc,
    output reg collect_en,
    output reg [2:0] state_dbg,
    output reg [15:0] cycle_count_dbg
);

    localparam [2:0] IDLE    = 3'd0;
    localparam [2:0] LOAD    = 3'd1;
    localparam [2:0] STREAM  = 3'd2;
    localparam [2:0] DRAIN   = 3'd3;
    localparam [2:0] COLLECT = 3'd4;
    localparam [2:0] DONE    = 3'd5;

    localparam [15:0] STREAM_CYCLES = (2 * ARRAY_SIZE) - 1;
    // With registered operand forwarding and a registered collect stage,
    // the array needs one extra tail cycle so the far-corner result is stable
    // before collection.
    localparam [15:0] DRAIN_CYCLES  = ARRAY_SIZE;

    reg [2:0] state_reg;
    reg [15:0] phase_count_reg;

    // Sequential FSM state progression.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_reg       <= IDLE;
            phase_count_reg <= 16'd0;
        end else begin
            case (state_reg)
                IDLE: begin
                    phase_count_reg <= 16'd0;

                    if (start) begin
                        state_reg <= LOAD;
                    end
                end

                LOAD: begin
                    state_reg       <= STREAM;
                    phase_count_reg <= 16'd0;
                end

                STREAM: begin
                    // STREAM injects new operands for the skew window length.
                    if (phase_count_reg == (STREAM_CYCLES - 1)) begin
                        state_reg       <= DRAIN;
                        phase_count_reg <= 16'd0;
                    end else begin
                        phase_count_reg <= phase_count_reg + 16'd1;
                    end
                end

                DRAIN: begin
                    // DRAIN allows in-flight operands to finish reaching downstream PEs.
                    if (phase_count_reg == (DRAIN_CYCLES - 1)) begin
                        state_reg       <= COLLECT;
                        phase_count_reg <= 16'd0;
                    end else begin
                        phase_count_reg <= phase_count_reg + 16'd1;
                    end
                end

                COLLECT: begin
                    state_reg       <= DONE;
                    phase_count_reg <= 16'd0;
                end

                DONE: begin
                    state_reg       <= IDLE;
                    phase_count_reg <= 16'd0;
                end

                default: begin
                    state_reg       <= IDLE;
                    phase_count_reg <= 16'd0;
                end
            endcase
        end
    end

    // Debug cycle count for one full run.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cycle_count_dbg <= 16'd0;
        end else if (start) begin
            // Restart the debug cycle counter at the beginning of each run.
            cycle_count_dbg <= 16'd0;
        end else if (busy) begin
            // Count only active accelerator cycles and hold the final value after done.
            cycle_count_dbg <= cycle_count_dbg + 16'd1;
        end
    end

    // Combinational control outputs derived directly from the current FSM state.
    always @(*) begin
        busy       = 1'b0;
        done       = 1'b0;
        load_en    = 1'b0;
        stream_en  = 1'b0;
        compute_en = 1'b0;
        clear_acc  = 1'b0;
        collect_en = 1'b0;
        state_dbg  = state_reg;

        case (state_reg)
            IDLE: begin
                busy = 1'b0;
            end

            LOAD: begin
                busy      = 1'b1;
                load_en   = 1'b1;
                clear_acc = 1'b1;
            end

            STREAM: begin
                // Stream new edge operands while compute is active.
                busy       = 1'b1;
                stream_en  = 1'b1;
                compute_en = 1'b1;
            end

            DRAIN: begin
                // Stop injection but keep the array running until the pipeline tail clears.
                busy       = 1'b1;
                compute_en = 1'b1;
            end

            COLLECT: begin
                // Capture the final PE accumulator image in the output register stage.
                busy       = 1'b1;
                collect_en = 1'b1;
            end

            DONE: begin
                done = 1'b1;
            end

            default: begin
                busy = 1'b0;
            end
        endcase
    end

endmodule
