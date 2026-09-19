-- Habilitar extensão para geração de UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela de Utilizadores
CREATE TABLE usuario (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    cpf VARCHAR(14) UNIQUE NOT NULL,
    telefone VARCHAR(20),
    senha_hash VARCHAR(255) NOT NULL,
    tipo_perfil VARCHAR(20) NOT NULL -- 'IDOSO' ou 'CUIDADOR'
);

-- Vínculo entre Cuidador e Idoso
CREATE TABLE vinculo_cuidador (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_cuidador UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_idoso UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    parentesco VARCHAR(50)
);

-- Tabela de Medicamentos
CREATE TABLE medicamento (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_idoso UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    nome_remedio VARCHAR(100) NOT NULL,
    dosagem VARCHAR(50) NOT NULL,
    instrucoes_uso TEXT
);

-- Horários de Rotina do Medicamento
CREATE TABLE horario_rotina (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_medicamento UUID NOT NULL REFERENCES medicamento(id) ON DELETE CASCADE,
    horario_previsto TIME NOT NULL,
    periodo VARCHAR(20) NOT NULL -- 'MANHA', 'TARDE', 'NOITE'
);

-- Registos de Adesão (Histórico)
CREATE TABLE registro_adesao (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_horario UUID NOT NULL REFERENCES horario_rotina(id) ON DELETE CASCADE,
    data_registro DATE NOT NULL DEFAULT CURRENT_DATE,
    horario_tomado TIME,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE' -- 'TOMADO', 'PENDENTE', 'IGNORADO'
);

-- Consultas e Exames Médicos
CREATE TABLE compromisso_medico (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_idoso UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL, -- 'CONSULTA' ou 'EXAME'
    especialidade VARCHAR(100) NOT NULL,
    local_atendimento VARCHAR(255),
    data_hora TIMESTAMP NOT NULL,
    preparo TEXT
);

-- Notas de Apoio enviadas pelo Cuidador
CREATE TABLE nota_apoio (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_idoso UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_cuidador UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    mensagem TEXT NOT NULL,
    data_envio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);