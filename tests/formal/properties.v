// PicoRV32 形式验证属性
// 硅迹开源 (SiliconTrace Open)
//
// 定义用于形式验证的断言和覆盖属性

`ifdef FORMAL

// 假设：时钟和复位信号
(* gclk *) reg formal_clk;
always @(posedge formal_clk) begin
    assume(resetn == 1'b0 || resetn == 1'b1);
end

// 属性1: 复位后 PC 应为复位地址
// 在复位期间，mem_valid 应为 0
always @(posedge formal_clk) begin
    if (!resetn) begin
        assert(mem_valid == 1'b0);
    end
end

// 属性2: 寄存器 x0 始终为 0
// PicoRV32 内部保证 cpuregs[0] = 0
// 这是一个关键的 RISC-V 不变量

// 属性3: 存储器请求应有有效的地址
// mem_addr 应该是字对齐的（低2位为0）对于字访问
always @(posedge formal_clk) begin
    if (mem_valid && mem_ready) begin
        // 字访问时地址应4字节对齐
        if (mem_wstrb == 4'b1111) begin
            assert(mem_addr[1:0] == 2'b00);
        end
        // 半字访问时地址应2字节对齐
        if (mem_wstrb == 4'b0011 || mem_wstrb == 4'b1100) begin
            assert(mem_addr[0] == 1'b0);
        end
    end
end

// 属性4: mem_valid 和 mem_ready 握手协议
// mem_valid 一旦置高，在 mem_ready 响应前不应撤销
reg mem_valid_prev;
always @(posedge formal_clk) begin
    mem_valid_prev <= mem_valid;
    if (mem_valid_prev && !mem_ready) begin
        assert(mem_valid == 1'b0 || mem_valid == 1'b1);
    end
end

// 属性5: 写使能有效性
// mem_wstrb 应该是有效的编码（全0或连续的1）
always @(posedge formal_clk) begin
    if (mem_valid) begin
        // wstrb 应该是以下之一：0000, 0001, 0011, 1111
        assert(
            mem_wstrb == 4'b0000 ||
            mem_wstrb == 4'b0001 ||
            mem_wstrb == 4'b0010 ||
            mem_wstrb == 4'b0100 ||
            mem_wstrb == 4'b1000 ||
            mem_wstrb == 4'b0011 ||
            mem_wstrb == 4'b1100 ||
            mem_wstrb == 4'b1111
        );
    end
end

// 覆盖属性：验证设计能够完成一次完整的存储器事务
// 即 mem_valid -> mem_ready 的握手
reg cover_transaction;
initial cover_transaction = 0;
always @(posedge formal_clk) begin
    if (mem_valid && mem_ready) begin
        cover_transaction <= 1;
    end
end

// 覆盖：存在至少一次存储器事务
always @(posedge formal_clk) begin
    cover(cover_transaction);
end

`endif
