-- Criar o banco de dados (caso ainda não exista)
CREATE DATABASE IF NOT EXISTS viagens_colegas;
USE viagens_colegas;

--------------------------------------
-- Usuários (cadastro e login)
--------------------------------------
CREATE TABLE usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha VARCHAR(255) NOT NULL,
    telefone VARCHAR(20),
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--------------------------------------
-- Destinos
--------------------------------------
CREATE TABLE destinos (
    id_destino INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    pais VARCHAR(100),
    cidade VARCHAR(100),
    descricao TEXT
);

--------------------------------------
-- Hospedagem (ligada a um destino)
--------------------------------------
CREATE TABLE hospedagens (
    id_hospedagem INT AUTO_INCREMENT PRIMARY KEY,
    id_destino INT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    preco DECIMAL(10,2) NOT NULL,
    tipo VARCHAR(50),
    contato VARCHAR(100),
    FOREIGN KEY (id_destino) REFERENCES destinos(id_destino)
);

--------------------------------------
-- Viagens (criação de roteiro)
--------------------------------------
CREATE TABLE viagens (
    id_viagem INT AUTO_INCREMENT PRIMARY KEY,
    id_criador INT NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    id_destino INT NOT NULL,
    data_inicio DATE,
    data_fim DATE,
    FOREIGN KEY (id_criador) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (id_destino) REFERENCES destinos(id_destino)
);

--------------------------------------
-- Participantes das viagens (Party / Sala)
--------------------------------------
CREATE TABLE participantes (
    id_participante INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    id_usuario INT NOT NULL,
    confirmado BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

--------------------------------------
-- Chat em grupo (na Party / Sala de Viagem)
--------------------------------------
CREATE TABLE mensagens (
    id_mensagem INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    id_usuario INT NOT NULL,
    mensagem TEXT NOT NULL,
    data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

--------------------------------------
-- Votações e Sugestões (destinos, atividades, datas)
--------------------------------------
CREATE TABLE votacoes (
    id_votacao INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    tipo VARCHAR(50), -- destino, atividade, data
    descricao VARCHAR(255) NOT NULL,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem)
);

CREATE TABLE votos (
    id_voto INT AUTO_INCREMENT PRIMARY KEY,
    id_votacao INT NOT NULL,
    id_usuario INT NOT NULL,
    opcao VARCHAR(255) NOT NULL,
    data_voto TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_votacao) REFERENCES votacoes(id_votacao),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

--------------------------------------
-- Cronograma da viagem
--------------------------------------
CREATE TABLE cronogramas (
    id_cronograma INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    data_evento DATE NOT NULL,
    atividade VARCHAR(255) NOT NULL,
    horario TIME,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem)
);

--------------------------------------
-- Checklist interativo
--------------------------------------
CREATE TABLE checklists (
    id_checklist INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    item VARCHAR(255) NOT NULL,
    concluido BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem)
);

--------------------------------------
-- Controle financeiro
--------------------------------------
CREATE TABLE despesas (
    id_despesa INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    id_usuario INT NOT NULL, -- quem pagou
    descricao VARCHAR(255),
    valor DECIMAL(10,2) NOT NULL,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- Registro de pagamentos
CREATE TABLE pagamentos (
    id_pagamento INT AUTO_INCREMENT PRIMARY KEY,
    id_despesa INT NOT NULL,
    id_usuario INT NOT NULL, -- quem deve pagar
    valor_pago DECIMAL(10,2) DEFAULT 0,
    data_pagamento TIMESTAMP NULL,
    FOREIGN KEY (id_despesa) REFERENCES despesas(id_despesa),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

--------------------------------------
-- Transporte e Alimentação
--------------------------------------
CREATE TABLE transportes (
    id_transporte INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    tipo VARCHAR(50), -- passagem, transporte local
    empresa VARCHAR(100),
    preco DECIMAL(10,2),
    data DATE,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem)
);

CREATE TABLE alimentacoes (
    id_alimentacao INT AUTO_INCREMENT PRIMARY KEY,
    id_viagem INT NOT NULL,
    descricao VARCHAR(150) NOT NULL,
    preco DECIMAL(10,2),
    data DATE,
    FOREIGN KEY (id_viagem) REFERENCES viagens(id_viagem)
);

CREATE TABLE rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_criador INT NOT NULL,
    name VARCHAR(100),
    destination VARCHAR(100),
    start_date DATE,
    end_date DATE,
    budget DECIMAL(10,2),
    description TEXT,
    code VARCHAR(10) UNIQUE,
    FOREIGN KEY (id_criador) REFERENCES usuarios(id_usuario)
);

CREATE TABLE IF NOT EXISTS user_rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    room_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES usuarios(id_usuario),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

--------------------------------------
select * from usuarios;
select * from rooms;
