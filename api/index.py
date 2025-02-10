import pandas as pd
from flask import Flask, jsonify, request  # Upewnij się, że to jest!
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import numpy as np
import requests

app = Flask(__name__)

def load_data():
    recipes_url = "https://67a9cf6c6e9548e44fc4ff6e.mockapi.io/api/recipes/recipes"
    ratings_url = "https://67a9cf6c6e9548e44fc4ff6e.mockapi.io/api/recipes/ratings"
    
    recipes_response = requests.get(recipes_url)
    ratings_response = requests.get(ratings_url)

    if recipes_response.status_code == 200:
        recipes_data = recipes_response.json()  
    else:
        raise Exception("Błąd pobierania danych z API dla przepisów")

    if ratings_response.status_code == 200:
        ratings_data = ratings_response.json()  
    else:
        raise Exception("Błąd pobierania danych z API dla ocen")

    recipes_df = pd.DataFrame(recipes_data)
    ratings_df = pd.DataFrame(ratings_data)

    ratings_df = ratings_df.groupby(['UserId', 'RecipeId'], as_index=False)['Rating'].mean()

    return ratings_df, recipes_df

def get_similar_users(user_id, df, top_n=5):
    user_ratings = df.pivot(index='UserId', columns='RecipeId', values='Rating').fillna(0)
    user_similarity = cosine_similarity(user_ratings)
    user_similarity_df = pd.DataFrame(user_similarity, index=user_ratings.index, columns=user_ratings.index)
    

    similar_users = user_similarity_df[user_id].sort_values(ascending=False).iloc[1:top_n+1]
    #for user in similar_users.index:
       # print(user_ratings.loc[user].replace(0, np.nan).dropna())
        #print("\n")
    return similar_users.index.tolist()


def add_new_rating(user_id, recipe_id, rating, ratings_df):
    
    new_rating = pd.DataFrame({'UserId': [user_id], 'RecipeId': [recipe_id], 'Rating': [rating]})
    ratings_df = pd.concat([ratings_df, new_rating], ignore_index=True)
    
 
    ratings_df = ratings_df.groupby(['UserId', 'RecipeId'], as_index=False)['Rating'].mean()
    
    return ratings_df

def recommend_recipe(user_id, ratings_df, recipes_df):

    ratings_df = add_new_rating(user_id, recipe_id, rating, ratings_df)
    
    similar_users = get_similar_users(user_id, ratings_df)
 
    user_ratings = ratings_df.pivot(index='UserId', columns='RecipeId', values='Rating').fillna(0)

    similar_users_ratings = user_ratings.loc[similar_users]
   
    user_rated_recipes = user_ratings.loc[user_id]
    unrated_recipes = user_rated_recipes[user_rated_recipes == 0].index
   
    mean_ratings = similar_users_ratings[unrated_recipes].mean()

    likes_dict = recipes_df.set_index("RecipeId")["Number_of_likes"].to_dict()
    likes_scores = pd.Series({recipe: likes_dict.get(recipe, 0) for recipe in unrated_recipes})

    likes_scores = (likes_scores - likes_scores.min()) / (likes_scores.max() - likes_scores.min() + 1e-5)

    final_scores = mean_ratings + likes_scores
    recommended_recipe = final_scores.idxmax()
    
    return recommended_recipe

def update_and_recommend(user_id, recipe_id, rating, ratings_df, recipes_df):

    ratings_df = add_new_rating(user_id, recipe_id, rating, ratings_df)
  
    recommended_recipe = recommend_recipe(user_id, ratings_df, recipes_df)
    
    return recommended_recipe

def recommend_recipe_for_session(user_ids, ratings_df, recipes_df):

    session_ratings = ratings_df[ratings_df["UserId"].isin(user_ids)]
    
    session_mean_ratings = session_ratings.groupby("RecipeId")["Rating"].mean()
   
    likes_dict = recipes_df.set_index("RecipeId")["Number_of_likes"].to_dict()
    

    likes_scores = pd.Series({recipe: likes_dict.get(recipe, 0) for recipe in session_mean_ratings.index})
    likes_scores = (likes_scores - likes_scores.min()) / (likes_scores.max() - likes_scores.min() + 1e-5)  
    
    final_scores = session_mean_ratings + likes_scores
    
    recommended_recipe = final_scores.idxmax()
    
    return recommended_recipe


ratings_df, recipes_df = load_data()

#print(ratings_df['UserId'].unique())
#print(recipes_df['RecipeId'].unique())

user_id = 3  # ID użytkownika
recipe_id = 2  # ID ocenianego przepisu
rating = 4  # Nowa ocena

recommended_recipe = update_and_recommend(user_id, recipe_id, rating, ratings_df, recipes_df)
print(f"Nowa rekomendacja dla użytkownika {user_id}: {recommended_recipe}")
user_ids = [3, 6, 7]
recommended_recipe = recommend_recipe_for_session(user_ids, ratings_df, recipes_df)
print(f"Rekomendowany przepis dla sesji: {recommended_recipe}")


# Endpoint rekomendacji
@app.route('/recommend', methods=['GET'])
def recommend():
    user_id = request.args.get('user_id', type=int)
    session_ids = request.args.getlist('session_id', type=int)
    
    if user_id:
        recommended_recipe = recommend_recipe(user_id, ratings_df, recipes_df)
        
        # Przekonwertuj recommended_recipe na int, aby upewnić się, że jest serializowane
        recommended_recipe = int(recommended_recipe)
        
        return jsonify({"user_id": user_id, "recommended_recipe": recommended_recipe})
    
    if session_ids:
        recommended_recipe = recommend_recipe_for_session(session_ids, ratings_df, recipes_df)
        
        # Przekonwertuj recommended_recipe na int
        recommended_recipe = int(recommended_recipe)
        
        return jsonify({"session_users": session_ids, "recommended_recipe": recommended_recipe})
    
    return jsonify({"error": "Brak wymaganych parametrów"}), 400

# Uruchomienie serwera Flask
if __name__ == '__main__':
    app.run(debug=True)
