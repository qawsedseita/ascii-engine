Projeto ASCII Engine atualizado para o checkpoint de 2026-10-30. Leia `HANDOFF.md` e `AI_GUIDE.md` antes de continuar.

Estado: stages 1–8 concluídos, 71 testes passando com `python3 -m unittest discover -s tests -t .`. Inclui conversor de estilos, mapas, imagem→ASCII, mundo turn-based, efeitos/UI, áudio, plugins, API de IA, CLI e exemplos de integração.

Próximo passo de manutenção: rode a suíte e os exemplos, confira os limites documentados (especialmente reprodução real de áudio não testada), gere `ascii-engine.zip` sem `.git`/`__pycache__` e entregue. O sandbox não tem rede, então o usuário publica no GitHub.
