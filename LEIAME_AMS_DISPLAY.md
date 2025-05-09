# Atualização do Bloco AMS no Dashboard

Este documento descreve as alterações feitas para melhorar a exibição dos dados AMS no dashboard do SquidBu.

## Mudanças Realizadas

1. **Alterações no Frontend (`static/js/script.js`)**:
   - Modificado o código para exibir a temperatura real onde antes havia o ícone 🌡️
   - Modificado o código para exibir a umidade real onde antes havia o ícone 💧
   - Alterado o indicador de "Restante" para mostrar o valor em gramas ao invés de porcentagem

2. **Alterações no Backend (`app.py`)**:
   - Adicionada lógica na rota `/status` para buscar os dados mais recentes dos sensores ESP32 de cada caixa
   - Os dados de temperatura, umidade e peso restante são incorporados na estrutura de dados AMS que é enviada ao frontend

## Como aplicar as alterações

Para aplicar essas alterações, reinicie o serviço Flask:

```bash
# Se tiver permissões de sudo
sudo systemctl restart flask_app

# Ou usando o script restart_flask.py
python restart_flask.py

# Ou manualmente encerrando o processo atual e iniciando um novo
pkill -f "python.*SquidStart.py"
python SquidStart.py
```

## Verificando a Implementação

Após reiniciar o serviço, verifique:

1. Abra o navegador e acesse o dashboard do SquidBu
2. O bloco AMS deve mostrar:
   - A temperatura real no lugar do ícone 🌡️
   - A umidade real no lugar do ícone 💧
   - O valor em gramas ao lado de "Restante:" para cada bandeja

## Solução de Problemas

Se os dados não aparecerem:

1. Verifique os logs para possíveis erros:
   ```bash
   tail -n 100 flask_app.log
   ```

2. Verifique se o ESP32 está enviando os dados corretamente:
   ```bash
   mosquitto_sub -t "filament_monitor/#" -v
   ```

3. Verifique os dados no banco de dados:
   ```python
   from db_manager import SensorManager
   data = SensorManager.get_recent_sensor_data(source="ESP32_Box1", limit=1)
   print(data)
   ``` 