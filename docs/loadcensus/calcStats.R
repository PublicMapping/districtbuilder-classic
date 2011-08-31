###  Helper R Script for Census Data loading
###  This merges the PL data into the shapefile block data and
###  Generates quantiles for the choropleths.
###     
###  NOTE: Since this is run in rpy, the results are visible to python
###  Limit use of values to q_*, sum_TOTPOP, and has_election_data -- others may change


# merge census and supplementary data
library(foreign) 
setwd('/projects/PublicMapping/data')
merged.df<-read.dbf("census_blocks.dbf",as.is=TRUE)

# check for the existence of election variables in the data, choose the # best one
electionvar <- names(merged.df)[charmatch (c("VOTE_DEM","GOV10_DEM","GOV09_DEM","GOV08_DEM",
"PRS10_DEM","PRS09_DEM","PRS08_DEM"),names(merged.df))]
electionvar<-electionvar[which(!is.na(electionvar))][1]
if (is.na(electionvar)) {        
	has_election_data<-0
} else {
	has_election_data<-1  
}

# compute quantiles

sum_TOTPOP <- sum(merged.df$TOTPOP,na.rm=TRUE)
myq <- function(x) {
        x<-na.omit(x)
        round(c(min(x),as.vector(quantile(x[x>0],probs=seq(.2,.8,0.2))),max(x)))
}

#TODO Refactor as matrix of {geography and variables} 
q_block_VAP <- myq(merged.df$VAP)
q_block_VAP_H <- myq(merged.df$VAP_H)
q_block_VAP_B <- myq(merged.df$VAP_B)
q_block_VAP_NA <- myq(merged.df$VAP_NA)
q_tract_VAP <-myq(aggregate(merged.df$VAP,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_VAP_H <-myq(aggregate(merged.df$VAP_B,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_VAP_B <-myq(aggregate(merged.df$VAP_H,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_VAP_NA <-myq(aggregate(merged.df$VAP_NA,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_county_VAP <-myq(aggregate(merged.df$VAP,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_VAP_H <-myq(aggregate(merged.df$VAP_B,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_VAP_B <-myq(aggregate(merged.df$VAP_H,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_VAP_NA <-myq(aggregate(merged.df$VAP_NA,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_block_TOTPOP <- myq(merged.df$TOTPOP)
q_block_TOTPOP_H <- myq(merged.df$TOTPOP_H)
q_block_TOTPOP_B <- myq(merged.df$TOTPOP_B)
q_block_TOTPOP_NA <- myq(merged.df$TOTPOP_NA)
q_tract_TOTPOP <-myq(aggregate(merged.df$TOTPOP,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_TOTPOP_H <-myq(aggregate(merged.df$TOTPOP_B,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_TOTPOP_B <-myq(aggregate(merged.df$TOTPOP_H,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_tract_TOTPOP_NA <-myq(aggregate(merged.df$TOTPOP_NA,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
q_county_TOTPOP <-myq(aggregate(merged.df$TOTPOP,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_TOTPOP_H <-myq(aggregate(merged.df$TOTPOP_B,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_TOTPOP_B <-myq(aggregate(merged.df$TOTPOP_H,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
q_county_TOTPOP_NA <-myq(aggregate(merged.df$TOTPOP_NA,by=list(merged.df$COUNTYFP10),sum,na.rm=T)[2])
if (has_election_data) {
        q_block_VOTE_DEM<- myq(merged.df$VOTE_DEM)
        q_tract_VOTE_DEM<-myq(aggregate(merged.df$VOTE_DEM,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
        q_county_VOTE_DEM<-myq(aggregate(merged.df$VOTE_DEM,by=list(merged.df$COUNTYP10),sum,na.rm=T)[2])
        q_block_VOTE_REP<- myq(merged.df$VOTE_REP)
        q_tract_VOTE_REP<-myq(aggregate(merged.df$VOTE_REP,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
        q_county_VOTE_REP<-myq(aggregate(merged.df$VOTE_REP,by=list(merged.df$COUNTYP10),sum,na.rm=T)[2])
        q_block_VOTE_TOT<- myq(merged.df$VOTE_TOT)
        q_tract_VOTE_TOT<-myq(aggregate(merged.df$VOTE_TOT,by=list(merged.df$TRACTCE10),sum,na.rm=T)[2])
        q_county_VOTE_TOT<-myq(aggregate(merged.df$VOTE_TOT,by=list(merged.df$COUNTYP10),sum,na.rm=T)[2])
}

