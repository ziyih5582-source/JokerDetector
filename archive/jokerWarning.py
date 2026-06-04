import tkinter as tk
from tkinter import messagebox

class JokerPopup:
    def __init__(self, root):
        self.root = root
        self.root.title("恋爱冷静期")
        # 全屏置顶，挡住微信
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="red")  # 扎眼的红色背景

        # 已输入次数
        self.count = 0
        self.target = 5

        # 显示大标题
        self.title_label = tk.Label(
            root, 
            text="⚠️ 您已触发小丑预警！⚠️", 
            font=("黑体", 40, "bold"),
            bg="red",
            fg="white"
        )
        self.title_label.pack(pady=50)

        # 显示已输入次数
        self.count_label = tk.Label(
            root,
            text=f"当前已输入：{self.count}/{self.target} 次",
            font=("黑体", 30),
            bg="red",
            fg="yellow"
        )
        self.count_label.pack(pady=30)

        # 输入框
        self.entry = tk.Entry(root, font=("黑体", 25), width=20)
        self.entry.pack(pady=20)
        self.entry.bind("<Return>", self.check_input)  # 按回车提交

        # 提示文字
        self.hint_label = tk.Label(
            root,
            text="请输入：我不是小丑（输完按回车）",
            font=("黑体", 20),
            bg="red",
            fg="white"
        )
        self.hint_label.pack(pady=20)

    def check_input(self, event):
        user_input = self.entry.get().strip()
        if user_input == "我不是小丑":
            self.count += 1
            self.count_label.config(text=f"当前已输入：{self.count}/{self.target} 次")
            self.entry.delete(0, tk.END)  # 清空输入框
            
            if self.count == self.target:
                messagebox.showinfo("恭喜", "冷静成功！暂时收回小丑称号！")
                self.root.destroy()  # 关闭弹窗
        else:
            messagebox.showerror("错误", "输入不对！你是不是还想当小丑？")
            self.entry.delete(0, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = JokerPopup(root)
    root.mainloop()
