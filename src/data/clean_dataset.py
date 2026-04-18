import os

# -----------------------------
# INPUT (paste your JSON parts)
# -----------------------------

corrupt_files = [
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/1984/Digamber_Dattatraya_Deshpande_vs_Savitribai_Dattatraya_Deshpande_And_on_15_February_1984_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2000/Commissioner_Of_Income_Tax_And_Ors_vs_Ranchi_Club_Ltd_on_1_August_2000_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2000/Commissioner_Of_Income_Tax_vs_Prithipal_Singh_And_Co_on_20_July_2000_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2003/Commnr_Of_Income_Tax_Mumbai_vs_Tata_Chemicals_Ltd_on_28_March_2003_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2003/Union_Of_India_Uoi_vs_Ajit_Jain_And_Anr_on_16_January_2003_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2013/M_S_Mutha_Associates_Ors_vs_State_Of_Maharashtra_Ors_on_4_July_2013_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2013/Union_Of_India_Ors_vs_Sanjay_Jethi_Anr_on_18_October_2013_1.txt",
    "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2014/Lekhraj_Bansal_vs_State_Of_Rajasthan_Anr_on_25_February_2014_1.txt"
]

duplicates = {
    "09bd44c74b7a4a0e": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/1957/The_Berar_Swadeshi_Vanaspathi_Others__vs_The_Municipal_Committee_Shfgaon_on_15_February_1957.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/1957/The_Berar_Swadeshi_Vanaspathi_Others_vs_The_Municipal_Committee_Shfgaon_on_15_February_1957_1.txt"
    ],
    "edbc16cdf22c9881": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_And_Ors_on_24_January_2024_1.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_on_24_January_2024_1.txt"
    ],
    "2d46847068219e38": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_And_Ors_on_31_January_2024_1.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_on_31_January_2024_1.txt"
    ],
    "164f0f88a39bad6f": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_And_Ors_on_6_March_2024_1.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/In_Re___T_N_Godavarman_Thirumulpad_vs_Union_Of_India_on_6_March_2024_1.txt"
    ],
    "e6e44061f69cb608": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/Sharif_Ahmad_vs_The_State_Of_Uttar_Pradesh_Home_on_1_May_2024_1.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/Vakil_Ahmad_vs_The_State_Of_Uttar_Pradesh_Home_on_1_May_2024_1.txt"
    ],
    "d2a783c2d2b1af5f": [
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/Vijay_Singh_Vijay_Kr_Sharma_vs_The_State_Of_Bihar_on_25_September_2024_1.txt",
        "/home/vxrun/LexiFusionNet/data/input/supreme_court_judgments_txt/2024/Vijay_Singh_Vijay_Kr_Sharma_vs_The_State_Of_Bihar_on_4_October_2024_1.txt"
    ]
}
# duplicates={}
# -----------------------------
# DELETE CORRUPT FILES
# -----------------------------
print("\nDeleting corrupt files...")
for file in corrupt_files:
    if os.path.exists(file):
        os.remove(file)
        print(f"Deleted: {file}")
    else:
        print(f"Not found: {file}")

# -----------------------------
# REMOVE DUPLICATES
# -----------------------------
print("\nRemoving duplicates...")

for hash_id, files in duplicates.items():
    # Keep the first file, delete the rest
    keep = files[0]
    remove = files[1:]

    print(f"\nGroup {hash_id}")
    print(f"Keeping: {keep}")

    for file in remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"Deleted duplicate: {file}")
        else:
            print(f"Not found: {file}")

print("\n✅ Cleanup complete.")