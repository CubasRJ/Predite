import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys

def verificar_credenciais(usuario, senha):
    usuario_correto = "hack"
    senha_correta = "etica"
    return usuario == usuario_correto and senha == senha_correta

def tentar_login():
    usuario = entrada_usuario.get()
    senha = entrada_senha.get()

    if verificar_credenciais(usuario, senha):
        messagebox.showinfo("Login", "Login bem-sucedido!")
        janela.destroy()

       
        if os.name == "nt":  # Windows
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                ["streamlit", "run", "teste.py"],
                creationflags=CREATE_NO_WINDOW
            )
    else:
        messagebox.showerror("Erro", "Usuário ou senha incorretos.")

janela = tk.Tk()
janela.title("Login")
janela.geometry("300x150")
janela.resizable(False, False)

tk.Label(janela, text="Usuário:").pack(pady=5)
entrada_usuario = tk.Entry(janela)
entrada_usuario.pack()

tk.Label(janela, text="Senha:").pack(pady=5)
entrada_senha = tk.Entry(janela, show="*")
entrada_senha.pack()

botao_login = tk.Button(janela, text="Login", command=tentar_login)
botao_login.pack(pady=10)

janela.mainloop()
