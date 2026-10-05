install_if_missing <- function(pkgs) {
  missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0) {
    install.packages(missing, repos = "https://cloud.r-project.org")
  }
}

install_if_missing(c("MatchIt", "arrow", "cobalt", "dplyr"))

library(MatchIt)
library(arrow)
library(cobalt)
library(dplyr)

# The two group files from adapting-cosmos/build_group_parquet.py.
# On the VM, point these at the real hat_group.parquet and control_group.parquet.
hat <- read_parquet("tutorial/synthetic_cosmos/hat/hat_group.parquet")
control <- read_parquet("tutorial/synthetic_cosmos/ctrl/control_group.parquet")

cohort <- bind_rows(hat, control) |>
  filter(EligibleForMatching == 1) |>
  mutate(
    HaT_Flag = as.integer(HaT_Flag),
    Sex = factor(Sex),
    Race = factor(Race),
    Ethnicity = factor(Ethnicity),
    IndexQuarter = factor(IndexQuarter)
  )

match <- matchit(
  HaT_Flag ~ AgeAtIndex +
    YearsBeforeIndex +
    YearsAfterIndex +
    log1p(ClinicVisits365Before) +
    Race +
    Ethnicity,
  data = cohort,
  method = "nearest",
  distance = "glm",
  exact = ~ Sex + IndexQuarter,
  ratio = 10,
  replace = FALSE,
  caliper = 0.2,
  std.caliper = TRUE
)

print(summary(match, un = FALSE))

dir.create("tutorial/work", showWarnings = FALSE)
matched <- match.data(match)
write_parquet(matched, "tutorial/work/matched_cohort.parquet")

png("tutorial/work/matchit_balance_love_plot.png", width = 1200, height = 800)
print(love.plot(match, threshold = 0.1))
dev.off()
