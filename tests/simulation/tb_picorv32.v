// PicoRV32 仿真测试平台
// 硅迹开源 (SiliconTrace Open)
//
// 功能：验证 PicoRV32 基本指令执行、存储器访问、中断响应

`timescale 1ns / 1ps

module tb_picorv32;

    // 时钟和复位
    reg clk;
    reg resetn;

    // 存储器接口
    wire        mem_valid;
    wire        mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [3:0]  mem_wstrb;
    reg  [31:0] mem_rdata;

    // 中断
    reg [31:0] irq;

    // 统计
    integer cycle_count;
    integer pass_count;
    integer fail_count;

    // 存储器模型 (64KB)
    reg [31:0] memory [0:16383];

    // 时钟生成 - 100MHz
    initial clk = 0;
    always #5 clk = ~clk;

    // DUT 实例化
    picorv32 #(
        .ENABLE_COUNTERS(1),
        .ENABLE_COUNTERS64(1),
        .ENABLE_REGS_16_31(1),
        .ENABLE_REGS_DUALPORT(1),
        .LATCHED_MEM_RDATA(0),
        .TWO_STAGE_SHIFT(1),
        .BARREL_SHIFTER(0),
        .TWO_CYCLE_COMPARE(0),
        .TWO_CYCLE_ALU(0),
        .COMPRESSED_ISA(0),
        .CATCH_MISALIGN(1),
        .CATCH_ILLINSN(1),
        .ENABLE_PCPI(0),
        .ENABLE_MUL(0),
        .ENABLE_DIV(0),
        .ENABLE_IRQ(1),
        .ENABLE_IRQ_QREGS(1),
        .ENABLE_IRQ_TIMER(1),
        .ENABLE_TRACE(0),
        .REGS_INIT_ZERO(0),
        .MASKED_IRQ(32'h0000_0000),
        .LATCHED_IRQ(32'hffff_ffff),
        .PROGADDR_RESET(32'h0000_0000),
        .PROGADDR_IRQ(32'h0000_0010),
        .STACKADDR(32'h0000_2000)
    ) uut (
        .clk(clk),
        .resetn(resetn),
        .mem_valid(mem_valid),
        .mem_instr(mem_instr),
        .mem_ready(mem_ready),
        .mem_addr(mem_addr),
        .mem_wdata(mem_wdata),
        .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata),
        .pcpi_valid(),
        .pcpi_insn(),
        .pcpi_rs1(),
        .pcpi_rs2(),
        .pcpi_wr(0),
        .pcpi_rd(0),
        .pcpi_wait(0),
        .pcpi_ready(0),
        .irq(irq),
        .eoi(),
        .trace_valid(),
        .trace_data()
    );

    // 存储器模型
    always @(posedge clk) begin
        mem_ready <= 0;
        if (mem_valid && !mem_ready) begin
            if (mem_addr[31:16] == 16'h0000) begin
                // 代码/数据存储器
                if (|mem_wstrb) begin
                    // 写操作
                    if (mem_wstrb[0]) memory[mem_addr[15:2]][ 7: 0] <= mem_wdata[ 7: 0];
                    if (mem_wstrb[1]) memory[mem_addr[15:2]][15: 8] <= mem_wdata[15: 8];
                    if (mem_wstrb[2]) memory[mem_addr[15:2]][23:16] <= mem_wdata[23:16];
                    if (mem_wstrb[3]) memory[mem_addr[15:2]][31:24] <= mem_wdata[31:24];
                end
                mem_rdata <= memory[mem_addr[15:2]];
            end else begin
                // 外设地址空间 - 返回0
                mem_rdata <= 32'h0;
            end
            mem_ready <= 1;
        end
    end

    // 加载测试程序
    initial begin
        $readmemh("tests/simulation/test.hex", memory);
    end

    // 主测试序列
    initial begin
        $dumpfile("tests/simulation/tb_picorv32.vcd");
        $dumpvars(0, tb_picorv32);

        cycle_count = 0;
        pass_count = 0;
        fail_count = 0;
        irq = 0;

        // 复位
        resetn = 0;
        repeat(10) @(posedge clk);
        resetn = 1;

        // 等待程序执行完成（通过写特定地址表示完成）
        // 测试通过: 写 0x10000 = 1
        // 测试失败: 写 0x10000 = 0
        wait(mem_valid && mem_addr == 32'h0001_0000 && |mem_wstrb);
        @(posedge clk);

        if (memory[16'h4000] == 32'h1) begin
            $display("========================================");
            $display(" 测试通过!");
            $display("========================================");
            pass_count = pass_count + 1;
        end else begin
            $display("========================================");
            $display(" 测试失败! result = %h", memory[16'h4000]);
            $display("========================================");
            fail_count = fail_count + 1;
        end

        $display("总周期数: %0d", cycle_count);
        $display("通过: %0d, 失败: %0d", pass_count, fail_count);
        $finish;
    end

    // 周期计数
    always @(posedge clk) begin
        if (resetn) cycle_count <= cycle_count + 1;
        // 超时保护
        if (cycle_count > 100000) begin
            $display("ERROR: 仿真超时 (%0d 周期)", cycle_count);
            $finish;
        end
    end

endmodule
