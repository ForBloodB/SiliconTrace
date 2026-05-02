// Small SKY130 demo design for flow regression.
module blinky_counter (
    input wire clk,
    input wire resetn,
    input wire enable,
    output wire pulse,
    output wire [7:0] gpio
);
    reg [7:0] counter;

    always @(posedge clk) begin
        if (!resetn) begin
            counter <= 8'd0;
        end else if (enable) begin
            counter <= counter + 8'd1;
        end
    end

    assign gpio = counter;
    assign pulse = &counter;
endmodule
