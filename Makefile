DB = PizzaParty.db

.PHONY: all clean

all: $(DB)

$(DB):
	@rm -f $(DB)
	sqlite3 $(DB) < pp_creation.sql
	sqlite3 $(DB) < pp_indices.sql
	sqlite3 $(DB) < pp_triggers.sql
	@echo "$(DB) created successfully."

clean:
	@rm -f $(DB)
	@echo "$(DB) removed."