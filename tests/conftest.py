"""Configuração comum dos testes."""

# Força o backend não-interativo do Matplotlib antes de qualquer import do
# pacote (que carrega visualization -> pyplot). Mantém os testes headless.
import matplotlib

matplotlib.use("Agg")
