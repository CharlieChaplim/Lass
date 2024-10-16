import asyncio
import discord
from discord.ext import commands
import sqlite3
import datetime
import random
import validators
import json
import re
import schedule
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents, case_insensitive=True)


# Conectando ao banco de dados SQLite
conn = sqlite3.connect('powers.db')
c = conn.cursor()

# Criando tabelas necessárias
c.execute('''
          CREATE TABLE IF NOT EXISTS powers
          (id INTEGER PRIMARY KEY, 
          name TEXT, 
          description TEXT, 
          advantage TEXT, 
          disadvantage TEXT,
          image TEXT,
          creator_id INTEGER)
          ''')
c.execute('''
          CREATE TABLE IF NOT EXISTS characters
          (id INTEGER PRIMARY KEY, 
          name TEXT, 
          description TEXT, 
          server TEXT, 
          image TEXT,
          creator_id INTEGER)
          ''')
c.execute('''
          CREATE TABLE IF NOT EXISTS rolls
          (id INTEGER PRIMARY KEY, 
          server_id INTEGER, 
          name TEXT, 
          options TEXT, 
          creator_id INTEGER)
          ''')
conn.commit()

# Verificar se o usuário é administrador
def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

# Carrega as rotinas do arquivo JSON ao iniciar
def load_rotinas():
    try:
        with open('rotinas.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Salva as rotinas no arquivo JSON
def save_rotinas():
    with open('rotinas.json', 'w') as f:
        json.dump(rotinas, f, indent=4)

# Dicionário para armazenar as rotinas
rotinas = load_rotinas()

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    # Reagendar todas as rotinas ao iniciar o bot
    for horario, info in rotinas.items():
        schedule.every().day.at(horario).do(lambda: asyncio.run_coroutine_threadsafe(
            send_message(info['chat_id'], info['mensagem']), bot.loop))

    check_rotinas.start()  # Inicia a verificação das rotinas

@bot.command()
@commands.check(is_admin)
async def rotina(ctx, horario: str, chat: int, *, mensagem: str):
    try:
        # Valida o formato do horário
        valid_format = re.match(r"^\d{2}:\d{2}(:\d{2})?$", horario)
        if not valid_format:
            await ctx.send("Formato de horário inválido. Use HH:MM ou HH:MM:SS.")
            return

        def format_message(msg):
            return re.sub(r'(^\w|\s\w)', lambda m: m.group().upper(), msg)

        formatted_message = format_message(mensagem)
        
        # Verifica se o horário já existe no dicionário
        if horario not in rotinas:
            rotinas[horario] = {}

        # Salva a rotina no dicionário, usando chat_id como chave secundária
        rotinas[horario][chat] = {
            'mensagem': formatted_message
        }
        save_rotinas()  # Salva as rotinas no arquivo JSON

        # Função para enviar a mensagem
        async def send_message(chat_id, message):
            channel = bot.get_channel(chat_id)
            if channel:
                await channel.send(message)

        # Agenda a rotina para o horário especificado
        schedule.every().day.at(horario).do(lambda: asyncio.run_coroutine_threadsafe(
            send_message(chat, formatted_message), bot.loop))

        await ctx.send(f"Rotina definida: `{horario}` no canal <#{chat}> com a mensagem:")
        await ctx.send(formatted_message)
    
    except Exception as e:
        await ctx.send(f"Ocorreu um erro: {str(e)}")
        
@bot.command()
@commands.check(is_admin)
async def deleterotina(ctx, horario: str, chat: int):
    if horario in rotinas:
        # Verifica se existe uma rotina específica para o horário e canal fornecidos
        if chat in rotinas[horario]:
            # Remove a rotina do dicionário
            del rotinas[horario][chat]
            
            # Se não houver mais rotinas para esse horário, remova a entrada de horário
            if not rotinas[horario]:
                del rotinas[horario]
            
            save_rotinas()  # Salva as mudanças no arquivo JSON

            await ctx.send(f"Rotina das {horario} no canal <#{chat}> foi removida com sucesso.")
        else:
            await ctx.send(f"Não foi encontrada nenhuma rotina para o horário {horario} no canal <#{chat}>.")
    else:
        await ctx.send(f"Não foi encontrada nenhuma rotina para o horário {horario}.")

@bot.command()
async def listrotinas(ctx):
    if not rotinas:
        await ctx.send("Nenhuma rotina definida no momento.")
    else:
        response = "**Rotinas Definidas:**\n"
        for horario, canais in rotinas.items():
            for chat_id, info in canais.items():
                response += f"- **Horário:** {horario} | **Canal:** <#{chat_id}> | **Mensagem:** {info['mensagem']}\n"
        await ctx.send(response)


# Função para traduzir textos
def translate(text, lang):
    translations = {
        "Character added successfully!": "Personagem adicionado com sucesso!",
        "Character deleted successfully!": "Personagem excluído com sucesso!",
        "Character not found.": "Personagem não encontrado.",
        "Character updated successfully!": "Personagem atualizado com sucesso!",
        "Invalid field. Valid fields are: description, server, image.": "Campo inválido. Campos válidos são: description, server, image.",
        "No powers available.": "Não há poderes disponíveis no momento.",
        "Roll created successfully!": "Roll criado com sucesso!",
        "Roll deleted successfully!": "Roll excluído com sucesso!",
        "Roll not found.": "Roll não encontrado.",
        "Power List": "Lista de Poderes"
    }
    return translations.get(text, text)

# Comando para adicionar um novo poder (somente para administradores)
@bot.command()
@commands.check(is_admin)
async def addpower(ctx, name: str, description: str, advantage: str, disadvantage: str, image: str = None):
    c.execute("INSERT INTO powers (name, description, advantage, disadvantage, image, creator_id) VALUES (?, ?, ?, ?, ?, ?)", 
              (name, description, advantage, disadvantage, image, ctx.author.id))
    conn.commit()
    await ctx.send(f'Poder "{name}" adicionado com sucesso!')

# Comando para listar todos os poderes
@bot.command()
async def listpowers(ctx):
    c.execute("SELECT name, description, advantage, disadvantage, image FROM powers")
    powers = c.fetchall()
    if not powers:
        await ctx.send(translate("No powers available.", "pt"))
        return

    pages = []
    for power in powers:
        embed = discord.Embed(title=power[0], description=power[1], color=discord.Color.blue())
        embed.add_field(name="Vantagem", value=power[2], inline=False)
        embed.add_field(name="Desvantagem", value=power[3], inline=False)
        if power[4]:
            embed.set_image(url=power[4])
        pages.append(embed)

    message = await ctx.send(embed=pages[0])

    # Adiciona reações de navegação
    await message.add_reaction('◀️')
    await message.add_reaction('▶️')

    # Função para manipular a paginação
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['◀️', '▶️']

    current_page = 0
    while True:
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            if str(reaction.emoji) == '▶️':
                current_page += 1
                if current_page >= len(pages):
                    current_page = 0
                await message.edit(embed=pages[current_page])
                await message.remove_reaction(reaction, user)
            elif str(reaction.emoji) == '◀️':
                current_page -= 1
                if current_page < 0:
                    current_page = len(pages) - 1
                await message.edit(embed=pages[current_page])
                await message.remove_reaction(reaction, user)
        except asyncio.TimeoutError:
            break

# Comando para excluir um poder
@bot.command()
async def deletepower(ctx, name: str):
    c.execute("DELETE FROM powers WHERE name = ? AND creator_id = ?", (name, ctx.author.id))
    conn.commit()
    if c.rowcount:
        await ctx.send(f'Poder "{name}" excluído com sucesso!')
    else:
        await ctx.send(f'Você não possui um poder chamado "{name}" ou não tem permissão para excluí-lo.')

# Comando para buscar um poder específico
@bot.command()
async def getpower(ctx, name: str):
    c.execute("SELECT name, description, advantage, disadvantage, image FROM powers WHERE name = ?", (name,))
    power = c.fetchone()
    if power:
        embed = discord.Embed(title=power[0], description=power[1], color=discord.Color.green())
        embed.add_field(name="Vantagem", value=power[2], inline=False)
        embed.add_field(name="Desvantagem", value=power[3], inline=False)
        if power[4]:
            embed.set_image(url=power[4])
        await ctx.send(embed=embed)
    else:
        await ctx.send(f'Poder "{name}" não encontrado.')

# Comando para editar um poder existente
@bot.command()
async def editpower(ctx, name: str, field: str, value: str):
    valid_fields = ["description", "advantage", "disadvantage", "image"]
    field_translation = {
        "description": "Descrição",
        "advantage": "Vantagem",
        "disadvantage": "Desvantagem",
        "image": "Imagem"
    }
    if field not in valid_fields:
        await ctx.send(translate("Invalid field. Valid fields are: description, advantage, disadvantage, image.", "pt"))
        return
    query = f"UPDATE powers SET {field} = ? WHERE name = ? AND creator_id = ?"
    c.execute(query, (value, name, ctx.author.id))
    conn.commit()
    if c.rowcount:
        await ctx.send(f'{field_translation[field]} do poder "{name}" atualizada com sucesso!')
    else:
        await ctx.send(f'Você não possui um poder chamado "{name}" ou não tem permissão para editá-lo.')

# Comando para editar o prefixo
@bot.command()
async def editprefix(ctx, new_prefix: str):
    bot.command_prefix = new_prefix
    await ctx.send(f'Prefixo atualizado para "{new_prefix}"')

# Remover o comando help padrão e adicionar o personalizado
bot.remove_command('help')

@bot.command(name='help')
async def custom_help(ctx):
    response = (
        "**Comandos Disponíveis:**\n"
        "`$addpower <nome> <descrição> <vantagem> <desvantagem> [imagem]` - Adiciona um novo poder (somente administradores)\n"
        "`$listpowers` - Lista todos os poderes\n"
        "`$deletepower <nome>` - Exclui um poder\n"
        "`$getpower <nome>` - Exibe os detalhes de um poder específico\n"
        "`$editpower <nome> <campo> <valor>` - Edita um campo de um poder específico\n"
        "`$editprefix <novo_prefixo>` - Edita o prefixo dos comandos do bot\n"
        "`$Prandom` - Mostra um poder aleatório\n"
        "`$pergunta <pergunta>` - Responde uma pergunta com respostas pré-definidas\n"
        "`$addcharacter <nome> <descrição> <servidor> [imagem]` - Adiciona um novo personagem\n"
        "`$listcharacters` - Lista todos os personagens\n"
        "`$deletecharacter <nome>` - Exclui um personagem\n"
        "`$getcharacter <nome>` - Exibe os detalhes de um personagem específico\n"
        "`$editcharacter <nome> <campo> <valor>` - Edita um campo de um personagem específico\n"
        "`$avatar [@usuario|ID]` - Mostra o avatar do usuário ou do usuário especificado\n"
        "`$rollcreate <nome> <opções>` - Cria um novo roll (somente administradores)\n"
        "`$rolldelete <nome>` - Exclui um roll (somente administradores)\n"
        "`$roll <nome>` - Escolhe uma opção aleatória de um roll\n"
        "`$choose <opções>` - Escolhe uma opção aleatória das opções fornecidas\n"    
        "`$dado xdy` - Rola um dado com x dados de y lados\n"
        "`$convertimage` - Converte uma imagem para link.\n" 
        "`$ban <usuário> [motivo]` - Bane um usuário do servidor (requer permissões de banir membros)\n"
        "`$kick <usuário> [motivo]` - Expulsa um usuário do servidor (requer permissões de expulsar membros)\n"
        "`$rotina <horário> <ID do Chat> <mensagem>` - Define uma rotina diária no horário especificado\n"
        "`$listrotinas` - Lista todas as rotinas definidas\n"
        "`$deleterotina <horário> <ID do Chat>` - Remove uma rotina no horário especificado\n"
    )
    await ctx.send(response)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name='$help Mommy Lass'))
    print(f'Bot conectado como {bot.user}')


# Comando para exibir o avatar do usuário ou de um usuário especificado
@bot.command()
async def avatar(ctx, user: discord.User = None):
    user = user or ctx.author
    await ctx.send(user.avatar.url)

# Comando para exibir um poder aleatório
@bot.command()
async def Prandom(ctx):
    c.execute("SELECT name, description, advantage, disadvantage, image FROM powers ORDER BY RANDOM() LIMIT 1")
    power = c.fetchone()
    if power:
        embed = discord.Embed(
            title=power[0],
            description=power[1],
            color=discord.Color.blue()  # Escolha uma cor para o embed
        )
        embed.add_field(name="Vantagem", value=power[2], inline=False)
        embed.add_field(name="Desvantagem", value=power[3], inline=False)
        if power[4]:
            embed.set_image(url=power[4])
        await ctx.send(embed=embed)
    else:
        await ctx.send(translate("No powers available.", "pt"))

# Comando para responder perguntas com easter eggs
@bot.command()
async def pergunta(ctx, *, question: str):
    responses = [
        "Sim", "Não", "Com certeza", "Nem ferrando", "Tem duvidas?", 
        "Tenho minhas duvidas", "Talvez", "Pergunta pro Carlim", "Capaz", "Se quiser sim mano"
    ]
    easter_eggs = {
        "Yandere Lotus": "Não me envolvo com essas parada.",
        "Vou te nerfar": f"Eu te nerfo antes! **Nerfa {ctx.author.mention}**",
        "Mediador": "O metavekh... Como é lindo os mistérios dessa praga... Não vou te contar nada.",
        "Mergulhadores": "Ei... Eles não estão por perto né?",
        "Observadores": "Como esse cara são irritantes... **Despawna um observador aleatorio**",
        "Tia do Gusta": "AUREA? CADE? ONDE?",
        "conte sua lore": "Ah sim, então você quer saber minha história? Eu sou a líder dos mergulhadores... Não posso te contar mais sobre isso.",
        "Yin": "Ah sim, a gentil Yin... Preciso fazer uma visita a ela.",
        "Emissor": "Emissor? Odeio quando ele me ignora.",
        "Mandy": "A cópia bem feita dos mergulhadores? Hehe.",
        "Bruxa": "A bruxa... Sabia que seu nome é %ßðßðéþ©?",
        "Kaitostem": "A velha bruxa é uma mediadora de verdade?",
        "ʞɔ Lu ЯΛ Rakku KKЦ ck n˥": "Mano... Primeiramente, como você digitou isso certo? Segundamente, não fale com esse cara.",
        "Lass... E aquilo?": "https://tenor.com/view/peter-parker-peter-parker-tempted-tempted-gif-23970167",
        "2015": "https://tenor.com/view/jujutsu-kaisen-jujutsu-kaisen-yuuji-itadori-itadori-gif-19729870",
        "Yui": "Não falamos da Yui... **Sai do Local antes que ela nerfe minha versão com o Emissor**",
        "Ashley": "Talvez eu tenha a julgado mal...",
        "Lotus": "Lotus tem mais é que se fuder mesmo!"
    }

    triggered_eggs = [response for trigger, response in easter_eggs.items() if trigger.lower() in question.lower()]
    if triggered_eggs:
        if len(triggered_eggs) > 1:
            await ctx.send(
                "Calma ae paizão\n"
                "Está vendo aquela neblina brilhante?\n"
                "É a radiação deixada do Big Bang\n"
                "A explosão que criou o universo há 13,8 bilhões de anos, o que houve antes do Big Bang? Ninguém sabe.\n"
                "Não importa em que galáxia você viva, ao olhar para o universo"
            )
        else:
            await ctx.send(triggered_eggs[0])
    else:
        await ctx.send(random.choice(responses))


# Comando para adicionar um novo personagem
@bot.command()
async def addcharacter(ctx, name: str, description: str, server: str, image: str = None):
    # Verifica se a URL da imagem é válida antes de inserir no banco de dados
    if image and not validators.url(image):
        await ctx.send("URL da imagem inválida. Certifique-se de fornecer uma URL válida começando com http:// ou https://.")
        return
    
    c.execute("INSERT INTO characters (name, description, server, image, creator_id) VALUES (?, ?, ?, ?, ?)",
              (name, description, server, image, ctx.author.id))
    conn.commit()
    await ctx.send("Personagem adicionado com sucesso!")

@bot.command()
async def listcharacters(ctx):
    c.execute("SELECT name, description, server, image FROM characters")
    characters = c.fetchall()
    
    if not characters:
        await ctx.send("Não há personagens disponíveis no momento.")
        return
    
    index = 0
    embed = create_character_embed(characters[index])
    message = await ctx.send(embed=embed)
    
    # Adicionar botões de avançar e voltar
    await message.add_reaction('⬅️')
    await message.add_reaction('➡️')
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['⬅️', '➡️'] and reaction.message == message
    
    while True:
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            
            if str(reaction.emoji) == '➡️' and index < len(characters) - 1:
                index += 1
            elif str(reaction.emoji) == '⬅️' and index > 0:
                index -= 1
            
            embed = create_character_embed(characters[index])
            await message.edit(embed=embed)
            
            # Limpar todas as reações antes de adicionar novas
            await message.clear_reactions()
            await message.add_reaction('⬅️')
            await message.add_reaction('➡️')
        
        except asyncio.TimeoutError:
            break

# Comando para excluir um personagem
@bot.command()
async def deletecharacter(ctx, name: str):
    c.execute("DELETE FROM characters WHERE name = ? AND creator_id = ?", (name, ctx.author.id))
    conn.commit()
    if c.rowcount:
        await ctx.send(translate("Character deleted successfully!", "pt"))
    else:
        await ctx.send(translate("Character not found.", "pt"))

# Comando para exibir
@bot.command()
async def getcharacter(ctx, name: str):
    c.execute("SELECT name, description, server, image FROM characters WHERE name = ?", (name,))
    character = c.fetchone()
    
    if not character:
        await ctx.send("Personagem não encontrado.")
        return
    
    embed = create_character_embed(character)
    await ctx.send(embed=embed)

def create_character_embed(character):
    embed = discord.Embed(title=character[0], description=character[1], color=discord.Color.blue())
    embed.add_field(name="Servidor", value=character[2], inline=False)
    if character[3]:
        embed.set_image(url=character[3])
    return embed

# Comando para editar um personagem existente
@bot.command()
async def editcharacter(ctx, name: str, field: str, value: str):
    if field not in ["description", "server", "image"]:
        await ctx.send(translate("Invalid field. Valid fields are: description, server, image.", "pt"))
        return
    query = f"UPDATE characters SET {field} = ? WHERE name = ? AND creator_id = ?"
    c.execute(query, (value, name, ctx.author.id))
    conn.commit()
    if c.rowcount:
        await ctx.send(translate("Character updated successfully!", "pt"))
    else:
        await ctx.send(translate("Character not found.", "pt"))

# Comando para criar um novo roll (somente para administradores)
@bot.command()
@commands.check(is_admin)
async def rollcreate(ctx, name: str, *, options: str):
    name = name.lower()
    options = options.lower()

    c.execute("INSERT INTO rolls (server_id, name, options, creator_id) VALUES (?, ?, ?, ?)",
              (ctx.guild.id, name, options, ctx.author.id))
    conn.commit()
    await ctx.send(translate("Roll created successfully!", "pt"))

# Comando para excluir um roll (somente para administradores)
@bot.command()
@commands.check(is_admin)
async def rolldelete(ctx, name: str):
    name = name.lower()  # Convertendo o nome para minúsculas
    c.execute("DELETE FROM rolls WHERE server_id = ? AND name = ?", (ctx.guild.id, name))
    conn.commit()
    if c.rowcount:
        await ctx.send(translate("Roll deleted successfully!", "pt"))
    else:
        await ctx.send(translate("Roll not found.", "pt"))

# Comando para usar um roll
@bot.command()
async def roll(ctx, name: str):
    name = name.lower()  # Convertendo o nome para minúsculas
    c.execute("SELECT options FROM rolls WHERE server_id = ? AND name = ?", (ctx.guild.id, name))
    roll = c.fetchone()
    if roll:
        options = roll[0].split(',')
        await ctx.send(random.choice(options))
    else:
        await ctx.send(translate("Roll not found.", "pt"))

# Comando para escolher uma opção aleatória
@bot.command()
async def choose(ctx, *, options: str):
    options_list = options.split(',')
    await ctx.send(random.choice(options_list))

@bot.command()
async def dado(ctx, dice: str):
    try:
        rolls, sides = map(int, dice.lower().split('d'))
    except Exception as e:
        await ctx.send("Formato inválido. Use o formato xdy onde x é o número de dados e y é o número de lados.")
        return

    if rolls < 1 or rolls > 1000 or sides < 2 or sides > 99999999:
        await ctx.send("Por favor, mantenha o número de dados entre 1 e 1000 e o número de lados entre 2 e 99999999.")
        return

    results = [random.randint(1, sides) for _ in range(rolls)]
    await ctx.send(f"Resultados do dado {dice}: {', '.join(map(str, results))}")

# Comando de humor
@bot.command()
async def humor(ctx):
    user_id = ctx.author.id
    # Verificar o dia atual para determinar a resposta
    current_day = datetime.datetime.now().day
    random.seed(user_id + current_day)  # Seed para garantir a mesma resposta no mesmo dia

    # Respostas padrão
    responses = [
        "Estou Feliz", "Estou rindo", "Não to Tankando", "To triste", "To com raiva", "Estou Maliciosa"
    ]

    # Respostas personalizadas por ID
    custom_responses = {
        868235978643488898: "Estou com vontade de Nerfar alguém até o talo.",
        590264475899134037: "Estou com vontade de espalhar desinformação.",
        407192516077682688: "Estou tendo ezquisofrênia... Maldito seja vocês Lótus.",
        828368449344110592: "Estou aRUINAndo as coisas.",
        811919421416275968: "Estou me sentindo com sorte.",
        934910270659231765: "Estou com vontade de ler Marginal Tiete.",
        829818634637017090: "Morre praga."
    }

    if user_id in custom_responses:
        await ctx.send(custom_responses[user_id])
    else:
        await ctx.send(random.choice(responses))

@bot.command()
async def convertimage(ctx):
    if len(ctx.message.attachments) == 0:
        await ctx.send("Nenhuma imagem anexada encontrada.")
        return

    image_urls = [attachment.url for attachment in ctx.message.attachments]

    if image_urls:
        await ctx.send("Links das imagens anexadas:\n" + "\n".join([f"```{url}```" for url in image_urls]))
    else:
        await ctx.send("Nenhuma imagem anexada encontrada.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f'Usuário {member} foi banido por {reason}.')
    except Exception as e:
        await ctx.send(f'Erro ao banir {member}: {str(e)}')

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f'Usuário {member} foi expulso por {reason}.')
    except Exception as e:
        await ctx.send(f'Erro ao expulsar {member}: {str(e)}')

# Comando que apenas mostra o status personalizado e não pode ser executado
@bot.command()
async def status(ctx):
    await ctx.send('Este comando é apenas para mostrar o status personalizado do bot.')

# Inicializando o bot com o token
bot.run(TOKEN)