-- Edite este arquivo para personalizar a casa e os personagens.
return {
  totalAvatares = 2,           -- 1 ou 2
  comunicacao = true,         -- só funciona com 2 avatares
  velocidadeTempo = 1.0,
  avatares = {
    {
      nome = 'Avatar 1',
      arquivo = 'assets/avatar1.glb',
      corRoupa = { .27, .58, .88 },
      corPele = { .89, .69, .53 },
      -- Rotação extra: use math.pi caso o avatar importado apareça de costas.
      rotacao = 0,
      -- O GLB é automaticamente ajustado para 1,72 m de altura.
      altura = 1.72,
      personalidade = 'curioso'
    },
    {
      nome = 'Avatar 2',
      arquivo = 'assets/avatar2.glb',
      corRoupa = { .81, .43, .62 },
      corPele = { .64, .42, .31 },
      rotacao = 0,
      altura = 1.72,
      personalidade = 'sociavel'
    }
  }
}
