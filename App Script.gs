function doPost(e) {
  try {
    if (!e.postData || !e.postData.contents) {
      return ContentService.createTextOutput("Erro: Nenhum dado recebido.");
    }

    var dados = JSON.parse(e.postData.contents);
    Logger.log("JSON recebido: " + JSON.stringify(dados));

    var nomePagina = typeof dados.pagina === "string" ? dados.pagina : "Maquina 1";
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var aba = ss.getSheetByName(nomePagina);

    if (!aba) {
      aba = ss.insertSheet(nomePagina);
      Logger.log("Aba criada: " + nomePagina);
    }

    if (dados.cabecalho === true && Array.isArray(dados.linha)) {
      aba.clear();
      aba.appendRow(dados.linha);
      return ContentService.createTextOutput("Cabeçalho gravado com sucesso");
    }

    var dataHora = new Date();
    var temperatura = Number(dados.temperatura);
    var vibracao = Number(dados.vibracaoHz);
    var corrente = Number(dados.correnteA);

    Logger.log("Temperatura: " + temperatura);
    Logger.log("Vibração: " + vibracao);
    Logger.log("Corrente: " + corrente);

    if (isNaN(temperatura) || isNaN(vibracao) || isNaN(corrente)) {
      Logger.log("Erro: algum valor é NaN");
      return ContentService.createTextOutput("Erro: dados numéricos inválidos.");
    }

    aba.appendRow([dataHora, temperatura, vibracao, corrente]);
    return ContentService.createTextOutput("Dados gravados com sucesso");

  } catch (erro) {
    Logger.log("Erro interno: " + erro);
    return ContentService.createTextOutput("Erro interno: " + erro);
  }
}
