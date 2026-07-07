with open("api/app.py", "r") as f:
    content = f.read()

# Replace the inner `allow_origin_regex` CORSMiddleware with `allow_origins=settings.parsed_cors_origins`
# Oh, we had this:
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )
# It was added OUTSIDE of the first one, meaning it executes before the main one!
# Wait! Middlewares are added from inside out. The LAST one added wraps everything else and executes FIRST!
