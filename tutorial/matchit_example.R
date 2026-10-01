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

cohort <- read_parquet("tutorial/synthetic_parquets/match_ready_cohort.parquet") |>
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
    log1p(ClinicVisitCountPreIndex) +
    Race +
    Ethnicity,
  data = cohort,
  method = "nearest",
  distance = "glm",
  exact = ~ Sex + IndexQuarter,
  ratio = 4,
  replace = FALSE,
  caliper = 0.2,
  std.caliper = TRUE
)

print(summary(match))

matched <- match.data(match)
write_parquet(matched, "tutorial/synthetic_parquets/matchit_4to1_matched.parquet")

png("tutorial/synthetic_parquets/matchit_balance_love_plot.png", width = 1200, height = 800)
print(love.plot(match, threshold = 0.1))
dev.off()
