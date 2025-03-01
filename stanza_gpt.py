import stanza
import pandas as pd
from tqdm import tqdm
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
import sys
import warnings
import csv



##### file size #####

def size(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return len(lines)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return 0



##### dependency parsing #####

def dp(filename, *args):
    if len(args) == 0:
        start = 1
        end = 100000
    elif len(args) == 1:
        start = 1
        end = args[0]
    elif len(args) == 2:
        start = args[0]
        end = args[1]
    else:
        raise ValueError("The dp() function accepts a maximum of three arguments: filename, start, and end.")

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    if end is None:
        selected_lines = lines[start - 1:]
    else:
        selected_lines = lines[start - 1 : end]

    all_tokens = []

    stanza.download('en', verbose=False)
    nlp = stanza.Pipeline(lang='en',
                          processors='tokenize,pos,lemma,depparse',
                          use_gpu=True,
                          verbose=False)

    for idx, sentence in enumerate(tqdm(selected_lines, desc="Dependency Parsing"), start=start):
        doc = nlp(sentence)
        doc_dict = doc.to_dict()
        for sentence_data in doc_dict:
            for token in sentence_data:
                new_token = {"s_id": idx, **token}
                all_tokens.append(new_token)

    total_sentences = len(selected_lines)
    print(f"\n\nA total of {total_sentences} sentences have been processed.")
    print(f"Processed sentences from {start} to {start + total_sentences - 1}.")

    df = pd.DataFrame(all_tokens)
    df = df.drop(columns=['feats', 'misc'], errors='ignore')
    df = df.dropna(subset=['head'])
    df['head'] = df['head'].astype(int)

    return df



##### preview #####

def preview(df, s_id):
    total_sentences = df["s_id"].nunique()
    min_sentence = df["s_id"].min()
    max_sentence = df["s_id"].max()

    print(f"Total number of sentences: {total_sentences}")
    print(f"Sentence range: sentence {min_sentence} to {max_sentence}\n\n")
    print(f"<Preview of sentence ID {s_id}>\n\n")

    filtered_df = df[df["s_id"] == s_id]
    print(filtered_df)



##### chat #####

warnings.filterwarnings("ignore", message=".*ChatOpenAI.*deprecated.*")
warnings.filterwarnings("ignore", message=".*BaseChatModel.__call__.*deprecated.*")

def condition_loop():
    inclusion_conditions = []
    exclusion_conditions = []

    while True:
        print("Inclusion conditions (press Enter to finish):")
        cond = input().strip()
        if cond == "":
            break
        if cond == "exit":
            return None, None
        if cond == "reset":
            print("\n(((Resetting conditions.)))\n")
            inclusion_conditions = []
            exclusion_conditions = []
            return condition_loop()
        inclusion_conditions.append(cond)


    while True:
        print("Exclusion conditions (press Enter to finish):")
        cond = input().strip()
        if cond == "":
            break
        if cond == "exit":
            return None, None
        if cond == "reset":
            print("\n(((Resetting conditions.)))\n")
            inclusion_conditions = []
            exclusion_conditions = []
            return condition_loop()
        exclusion_conditions.append(cond)

    return inclusion_conditions, exclusion_conditions


def condition_to_code(conditions, api_key):
    if not conditions: 
        return ""
    query = "\n".join([f"- {cond}" for cond in conditions])
    prompt = f"""
              I have a pandas DataFrame named "df" that contains dependency-parsed sentences.
              Each row represents a token with the following columns:
              - s_id: sentence index
              - id: token's position in the sentence
              - text: token text
              - lemma: token lemma
              - upos: universal POS tag
              - xpos: language-specific POS tag
              - deprel: dependency relation
              - start_char: start index of token in the sentence
              - end_char: end index of token in the sentence

              Convert the following natural language query exactly into a single line of plain Python code that serves as a condition to filter "df".
              Do not add any extra conditions or modify any names or identifiers in any way.
              If the query references a .txt file (e.g., "file.txt"), you must call the load_list function with that exact file name (i.e. load_list("file.txt")) and then use the isin() method to check membership against the returned list.
              Do not wrap any identifier in load_list() unless it explicitly contains a .txt extension.
              When query is like "[COLUMN1] (when [COLUMN2] is [VALUE2]) is the same as [COLUMN3] (when [COLUMN4] is [VALUE4])", the code should be like "df[df['[COLUMN2]'] == '[VALUE2]']['[COLUMN1]'].isin(df[df['[COLUMN4]'] == '[VALUE4]']['[COLUMN3]'])".
              Use the exact COLUMN and VALUE names as suggested in the query, especially between the square brackets "[ ]".
              Output should be only the plain, executable code without any markdown formatting, such as triple backticks or language tags.
              {query}
    """

    llm = ChatOpenAI(temperature=0, openai_api_key=api_key, max_tokens=300)
    messages = [
        SystemMessage(content="You are a helpful assistant that generates error-free Python code."),
        HumanMessage(content=prompt)
    ]
    response = llm(messages)
    code = response.content.strip()

    if code.startswith("```"):
        code = code.strip("`")
        lines = code.splitlines()
        if lines and lines[0].strip().lower() == "python":
            code = "\n".join(lines[1:]).strip()

    return code


def chat(api_key):
        print("\n[[[Start chatting]]]\n")
        inclusions, exclusions = condition_loop()

        if inclusions is None or exclusions is None:
            print("\n(((Exiting the chat.)))")
            return None, None

        print(("\n------------------------------"))
        print("\n[[[Requested conditions]]]")
        print("\nInclusion conditions:")
        for cond in inclusions:
            print(f"-{cond}")
        print("\nExclusion conditions:")
        for cond in exclusions:
            print(f"-{cond}")

        print(("\n------------------------------"))
        print("\n[[[Generated code]]]")
        inclusion_codes = []
        exclusion_codes = []
        print("\nCode for inclusion conditions:")
        for cond in inclusions:
            inclusion_code = condition_to_code(cond, api_key)
            inclusion_codes.append(inclusion_code)
            print(f"-{inclusion_code}")
        print("\nCode for exclusion conditions:")
        for cond in exclusions:
            exclusion_code = condition_to_code(cond, api_key)
            exclusion_codes.append(exclusion_code)
            print(f"-{exclusion_code}")

        while True:
            print(("\n------------------------------"))
            user_input = input("\nDo you want to proceed with these conditions? (yes/no): ").strip().lower()
            if user_input == "exit":
                print("\n(((Exiting the chat.)))")
                return None, None
            elif user_input == "reset":
                print("\n(((Resetting conditions.)))\n")
                return chat(api_key)
            elif user_input in ["yes", "y"]:
                print("\n(((Code saved.)))")
                return inclusion_codes, exclusion_codes
            elif user_input in ["no", "n"]:
                print("\n==============================")
                print("(((Restarting condition input.)))\n")
                return chat(api_key)
            else:
                print("Invalid input. Please enter 'yes', 'no', 'exit', or 'reset'.\n")



##### apply #####

def apply(df, inclusion, exclusion):
    def load_list(file_name):
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            raise ValueError(f"Error reading {file_name}: {e}")

    
    filtered_df_list = []
    for inclusion_code in inclusion:
        eval_globals = {"pd": pd}
        if ".txt" in inclusion_code:
            eval_globals["load_list"] = load_list
        try:
            result = eval(inclusion_code, {**eval_globals, "df": df})
        except Exception as e:
            raise ValueError(f"Error evaluating inclusion code '{inclusion_code}': {e}")
        if isinstance(result, pd.Series) and result.dtype == bool:
            result = result.reindex(df.index, fill_value=False)
            filtered_df = df[result]
        elif isinstance(result, pd.DataFrame):
            filtered_df = result
        else:
            raise ValueError("Inclusion code did not return a valid DataFrame or Boolean Series.")
        filtered_df_list.append(filtered_df)

    common_s_ids = set.intersection(*[set(temp_df['s_id']) for temp_df in filtered_df_list])  
    final_filtered_df_list = [temp_df[temp_df['s_id'].isin(common_s_ids)] for temp_df in filtered_df_list]
    final_filtered_df = pd.concat(final_filtered_df_list).drop_duplicates(subset=['s_id'])


    excluded_df_list = []
    for exclusion_code in exclusion:
        eval_globals = {"pd": pd}
        if ".txt" in exclusion_code:
            eval_globals["load_list"] = load_list
        try:
            result = eval(exclusion_code, {**eval_globals, "df": df})  
        except Exception as e:
            raise ValueError(f"Error evaluating exclusion code '{exclusion_code}': {e}")
        if isinstance(result, pd.Series) and result.dtype == bool:
            result = result.reindex(df.index, fill_value=False)
            excluded_df = df[result]
        elif isinstance(result, pd.DataFrame):
            excluded_df = result
        else:
            raise ValueError("Exclusion code did not return a valid DataFrame or Boolean Series.")
        excluded_df_list.append(excluded_df)

    if excluded_df_list:
        excluded_s_ids = set.union(*[set(temp_df['s_id']) for temp_df in excluded_df_list])  
        final_filtered_df = final_filtered_df[~final_filtered_df['s_id'].isin(excluded_s_ids)] 

    selected_sids = final_filtered_df['s_id'].unique()
    selected_tokens = df[df['s_id'].isin(selected_sids)]

    final_sentences = []
    for s_id, group in selected_tokens.groupby('s_id'):
        sorted_group = group.sort_values(by='id')
        sentence = ""
        for _, token in sorted_group.iterrows():
            if token['upos'].lower() == 'punct':
                sentence = sentence.rstrip() + token['text']
            else:
                if sentence:
                    sentence += " " + token['text']
                else:
                    sentence = token['text']
        final_sentences.append((s_id, sentence))

    total_count = len(set([s_id for s_id, _ in final_sentences]))
    print(f"\nTotal filtered sentences: {total_count}\n")
    if total_count > 10:
        print("(Displaying the first 10 results)")
    for s_id, sent in final_sentences[:10]:
        print(f"{s_id}, {sent}")

    while True:
        file_name = input("\nSave the result (with extension .txt or .csv): ").strip()
        if file_name.lower() == 'exit':
            print("(((Exiting without saving)))")
            return  
        elif file_name.lower().endswith('.csv'):
            with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["s_id", "sentence"]) 
                for s_id, sent in final_sentences:
                    writer.writerow([s_id, sent])
            print(f"Results saved to {file_name}")
            break 
        elif file_name.lower().endswith('.txt'):
            with open(file_name, 'w', encoding='utf-8') as f:
                for s_id, sent in final_sentences:
                    f.write(f"{s_id}, {sent}\n")
            print(f"Results saved to {file_name}")
            break 
        else:
            print("***Invalid file name: please enter a file name ending with '.csv' or '.txt', or type 'exit' to quit.")
